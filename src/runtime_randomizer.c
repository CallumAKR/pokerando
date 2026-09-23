#include "global.h"
#include "item.h"
#include "new_game.h"
#include "move.h"
#include "pokemon.h"
#include "runtime_randomizer.h"
#include "starter_choose.h"
#include "randomizer_runtime_config.h"
#include "constants/abilities.h"
#include "constants/characters.h"
#include "constants/moves.h"
#include "constants/opponents.h"

static const enum Type sRegularTypes[] =
{
    TYPE_NORMAL,
    TYPE_FIGHTING,
    TYPE_FLYING,
    TYPE_POISON,
    TYPE_GROUND,
    TYPE_ROCK,
    TYPE_BUG,
    TYPE_GHOST,
    TYPE_STEEL,
    TYPE_FIRE,
    TYPE_WATER,
    TYPE_GRASS,
    TYPE_ELECTRIC,
    TYPE_PSYCHIC,
    TYPE_ICE,
    TYPE_DRAGON,
    TYPE_DARK,
    TYPE_FAIRY,
};

#define RUNTIME_LEVEL_UP_CAPACITY 64
#define RUNTIME_TEACHABLE_CAPACITY 512
#define RUNTIME_EVOLUTION_CAPACITY 32

static EWRAM_DATA struct LevelUpMove sRuntimeLevelUpLearnset[RUNTIME_LEVEL_UP_CAPACITY];
#if RANDOMIZER_RUNTIME_TMS
static EWRAM_DATA u16 sRuntimeTeachableLearnset[RUNTIME_TEACHABLE_CAPACITY];
static EWRAM_DATA u16 sRuntimeTeachablePool[RUNTIME_TEACHABLE_CAPACITY];
static EWRAM_DATA u16 sRuntimeTeachablePoolCount;
extern const u16 gTutorMoves[];
#endif
#if RANDOMIZER_RUNTIME_EVOLUTIONS
static EWRAM_DATA struct Evolution sRuntimeEvolutions[RUNTIME_EVOLUTION_CAPACITY];
#endif
#if RANDOMIZER_RUNTIME_POKEMON_BST
static EWRAM_DATA u16 sRuntimeBstCache[NUM_SPECIES];
static EWRAM_DATA u32 sRuntimeBstCacheSeed;
#endif
#if RANDOMIZER_RUNTIME_ABILITIES
static EWRAM_DATA u16 sRuntimeAbilityFamilyCache[NUM_SPECIES];
#endif

static u32 Mix32(u32 value)
{
    value ^= value >> 16;
    value *= 0x7FEB352Du;
    value ^= value >> 15;
    value *= 0x846CA68Bu;
    value ^= value >> 16;
    return value;
}

u32 RuntimeRandomizerGetSaveSeed(void)
{
    u32 trainerId = 0;

    if (gSaveBlock2Ptr != NULL)
        trainerId = GetTrainerId(gSaveBlock2Ptr->playerTrainerId);

    return Mix32(trainerId ^ RANDOMIZER_RUNTIME_ROM_SALT ^ 0xA5C31F27u);
}

u32 RuntimeRandomizerHash(u32 domain, u32 key1, u32 key2, u32 key3)
{
    u32 value = RuntimeRandomizerGetSaveSeed();

    value = Mix32(value ^ (domain * 0x9E3779B9u));
    value = Mix32(value ^ key1);
    value = Mix32(value ^ (key2 * 0x85EBCA6Bu));
    value = Mix32(value ^ (key3 * 0xC2B2AE35u));
    return value;
}

static u32 GetOriginalBst(enum Species species)
{
    const struct SpeciesInfo *info = &gSpeciesInfo[species];

    return info->baseHP
         + info->baseAttack
         + info->baseDefense
         + info->baseSpeed
         + info->baseSpAttack
         + info->baseSpDefense;
}

static bool32 RawSpeciesEvolvesTo(enum Species source, enum Species target)
{
    const struct Evolution *evolutions = gSpeciesInfo[source].evolutions;
    u32 i;

    for (i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
    {
        if (evolutions[i].targetSpecies == target)
            return TRUE;
    }
    return FALSE;
}

static bool32 HasRawEvolutionParent(enum Species species)
{
    enum Species candidate;

    for (candidate = SPECIES_NONE + 1; candidate < NUM_SPECIES; candidate++)
    {
        if (RawSpeciesEvolvesTo(candidate, species))
            return TRUE;
    }
    return FALSE;
}

static bool32 HasRawEvolutionGrandparent(enum Species species)
{
    enum Species parent;

    for (parent = SPECIES_NONE + 1; parent < NUM_SPECIES; parent++)
    {
        if (RawSpeciesEvolvesTo(parent, species)
         && HasRawEvolutionParent(parent))
            return TRUE;
    }
    return FALSE;
}

static bool32 HasRawEvolutionChild(enum Species species)
{
    const struct Evolution *evolutions = gSpeciesInfo[species].evolutions;

    return evolutions != NULL && evolutions[0].method != EVOLUTIONS_END;
}

static bool32 HasRawEvolutionGrandchild(enum Species species)
{
    const struct Evolution *evolutions = gSpeciesInfo[species].evolutions;
    u32 i;

    for (i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
    {
        enum Species child = evolutions[i].targetSpecies;

        if (child > SPECIES_NONE && child < NUM_SPECIES
         && HasRawEvolutionChild(child))
            return TRUE;
    }
    return FALSE;
}

static enum Species GetMegaBaseSpecies(enum Species species)
{
    const u16 *forms = gSpeciesInfo[species].formSpeciesIdTable;
    u32 i;

    if (!gSpeciesInfo[species].isMegaEvolution || forms == NULL)
        return SPECIES_NONE;

    for (i = 0; forms[i] != FORM_SPECIES_END; i++)
    {
        enum Species candidate = (enum Species)forms[i];

        if (candidate > SPECIES_NONE && candidate < NUM_SPECIES
         && !gSpeciesInfo[candidate].isMegaEvolution
         && !gSpeciesInfo[candidate].isGigantamax)
            return candidate;
    }
    return SPECIES_NONE;
}

static u32 CalculateRuntimeTargetBst(enum Species species, u32 depth)
{
    u32 minimum;
    u32 maximum;
    enum Species megaBase;

    if (RANDOMIZER_RUNTIME_PROTECT_STATS(species))
        return GetOriginalBst(species);
    if (gSpeciesInfo[species].isPrimalReversion
     || gSpeciesInfo[species].isUltraBurst
     || gSpeciesInfo[species].isGigantamax
     || gSpeciesInfo[species].isTeraForm
     || gSpeciesInfo[species].isTotem)
        return GetOriginalBst(species);
    if (RANDOMIZER_RUNTIME_BST_MODE == 0)
        return GetOriginalBst(species);

    megaBase = GetMegaBaseSpecies(species);
    if (megaBase != SPECIES_NONE)
        return CalculateRuntimeTargetBst(megaBase, depth + 1) + 100;

    if (RANDOMIZER_RUNTIME_BST_MODE == 2)
    {
        minimum = RANDOMIZER_RUNTIME_BST_NATURAL_MIN;
        maximum = RANDOMIZER_RUNTIME_BST_NATURAL_MAX;
    }
    else if (HasRawEvolutionGrandparent(species))
    {
        minimum = 470;
        maximum = 650;
    }
    else if (HasRawEvolutionGrandchild(species))
    {
        minimum = 180;
        maximum = 350;
    }
    else if (HasRawEvolutionParent(species) && HasRawEvolutionChild(species))
    {
        minimum = 350;
        maximum = 470;
    }
    else if (HasRawEvolutionParent(species))
    {
        minimum = 400;
        maximum = 650;
    }
    else if (HasRawEvolutionChild(species))
    {
        minimum = 180;
        maximum = 450;
    }
    else
    {
        minimum = 180;
        maximum = 650;
    }

    if (RANDOMIZER_RUNTIME_BST_MODE == 1 && depth < 4)
    {
        enum Species parent;

        for (parent = SPECIES_NONE + 1; parent < NUM_SPECIES; parent++)
        {
            if (RawSpeciesEvolvesTo(parent, species))
            {
                u32 parentBst = CalculateRuntimeTargetBst(parent, depth + 1);

                minimum = max(minimum, parentBst + 25);
            }
        }
        if (minimum > maximum)
            minimum = maximum;
    }

    return minimum + RuntimeRandomizerHash(
        RUNTIME_DOMAIN_SPECIES_STAT, species, NUM_STATS, 0)
        % (maximum - minimum + 1);
}

static u32 GetRuntimeTargetBst(enum Species species)
{
#if RANDOMIZER_RUNTIME_POKEMON_BST
    u32 seed = RuntimeRandomizerGetSaveSeed();
    u32 bst;

    if (sRuntimeBstCacheSeed != seed)
    {
        CpuFill16(0, sRuntimeBstCache, sizeof(sRuntimeBstCache));
        sRuntimeBstCacheSeed = seed;
    }
    if (sRuntimeBstCache[species] != 0)
        return sRuntimeBstCache[species];

    bst = CalculateRuntimeTargetBst(species, 0);
    sRuntimeBstCache[species] = bst;
    return bst;
#else
    return GetOriginalBst(species);
#endif
}

static bool32 IsSpecialSpecies(enum Species species)
{
    const struct SpeciesInfo *info = &gSpeciesInfo[species];

    return info->isRestrictedLegendary
        || info->isSubLegendary
        || info->isMythical
        || info->isUltraBeast
        || info->isParadox
        || info->isTotem
        || info->isMegaEvolution
        || info->isPrimalReversion
        || info->isUltraBurst
        || info->isGigantamax
        || info->isTeraForm;
}

static bool32 IsRuntimeSpeciesCandidate(enum Species species,
                                        bool32 allowSpecial,
                                        bool32 similarBst,
                                        u32 originalBst)
{
    u32 candidateBst;

    if (species <= SPECIES_NONE || species >= NUM_SPECIES)
        return FALSE;
    if (!IsSpeciesEnabled(species))
        return FALSE;
    if (gSpeciesInfo[species].isMegaEvolution
     || gSpeciesInfo[species].isPrimalReversion
     || gSpeciesInfo[species].isUltraBurst
     || gSpeciesInfo[species].isGigantamax
     || gSpeciesInfo[species].isTeraForm
     || gSpeciesInfo[species].isTotem)
        return FALSE;
    if (!allowSpecial && IsSpecialSpecies(species))
        return FALSE;

    if (!similarBst)
        return TRUE;

    candidateBst = GetRuntimeTargetBst(species);
    return candidateBst + 50 >= originalBst
        && candidateBst <= originalBst + 50;
}

enum Species RuntimeRandomizerSpecies(u32 domain, u32 key1, u32 key2,
                                      enum Species originalSpecies,
                                      bool32 allowSpecial, bool32 similarBst)
{
    u32 attempt;
    u32 originalBst = 0;

    if (originalSpecies > SPECIES_NONE && originalSpecies < NUM_SPECIES)
        originalBst = GetRuntimeTargetBst(originalSpecies);

    for (attempt = 0; attempt < NUM_SPECIES * 2; attempt++)
    {
        enum Species candidate = 1 + RuntimeRandomizerHash(
            domain, key1, key2, attempt) % (NUM_SPECIES - 1);

        if (IsRuntimeSpeciesCandidate(candidate, allowSpecial,
                                      similarBst, originalBst))
            return candidate;
    }

    return originalSpecies;
}

static bool32 HasTwoEvolutionStages(enum Species species)
{
    u32 i;

    for (i = 0; i < RUNTIME_EVOLUTION_CAPACITY - 1; i++)
    {
        const struct Evolution *first = GetSpeciesEvolutions(species);
        enum Species middle;
        const struct Evolution *second;

        /* GetSpeciesEvolutions uses a shared runtime buffer, so reacquire the
         * first-stage list on every iteration before asking for the second. */
        if (first == NULL || first[i].method == EVOLUTIONS_END)
            break;
        middle = first[i].targetSpecies;
        if (middle <= SPECIES_NONE || middle >= NUM_SPECIES)
            continue;
        second = GetSpeciesEvolutions(middle);
        if (second != NULL && second[0].method != EVOLUTIONS_END)
            return TRUE;
    }

    return FALSE;
}

enum Species RuntimeRandomizerStarter(u32 slot, enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_STARTERS
    u32 attempt;

    for (attempt = 0; attempt < NUM_SPECIES * 2; attempt++)
    {
        enum Species candidate = RuntimeRandomizerSpecies(
            RUNTIME_DOMAIN_STARTER, slot, attempt, originalSpecies,
            FALSE, FALSE);
        u32 previousSlot;
        bool32 duplicate = candidate == originalSpecies;

        for (previousSlot = 0; previousSlot < slot && !duplicate; previousSlot++)
        {
            if (candidate == GetStarterPokemon(previousSlot))
                duplicate = TRUE;
        }

        if (!duplicate
         && (!RANDOMIZER_RUNTIME_STARTERS_THREE_STAGE
          || HasTwoEvolutionStages(candidate)))
            return candidate;
    }
#endif

    return originalSpecies;
}

enum Species RuntimeRandomizerWildSpecies(u32 area, u32 slot,
                                          enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_WILD
    u32 mapKey = ((u32)gSaveBlock1Ptr->location.mapGroup << 16)
               | gSaveBlock1Ptr->location.mapNum;
    u32 key1;
    u32 key2;

    if (RANDOMIZER_RUNTIME_WILD_MODE == 0)
    {
        key1 = originalSpecies;
        key2 = 0;
    }
    else if (RANDOMIZER_RUNTIME_WILD_MODE == 1)
    {
        key1 = mapKey;
        key2 = (area << 16) | slot;
    }
    else
    {
        key1 = mapKey ^ (area * 0x9E37u);
        key2 = originalSpecies;
    }

    return RuntimeRandomizerSpecies(
        RUNTIME_DOMAIN_WILD_SPECIES, key1, key2, originalSpecies,
        RANDOMIZER_RUNTIME_WILD_ALLOW_SPECIAL,
        RANDOMIZER_RUNTIME_WILD_SIMILAR_BST);
#else
    return originalSpecies;
#endif
}

enum Species RuntimeRandomizerStaticSpecies(u32 context, u32 slot,
                                            enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_STATICS
    u32 mapKey = ((u32)gSaveBlock1Ptr->location.mapGroup << 8)
               | gSaveBlock1Ptr->location.mapNum;
    u32 attempt;
    bool32 originalIsSpecial = IsSpecialSpecies(originalSpecies);

    for (attempt = 0; attempt < NUM_SPECIES * 2; attempt++)
    {
        enum Species candidate = 1 + RuntimeRandomizerHash(
            RUNTIME_DOMAIN_STATIC_SPECIES, mapKey, originalSpecies, attempt)
            % (NUM_SPECIES - 1);

        if (!IsRuntimeSpeciesCandidate(candidate, TRUE, FALSE, 0))
            continue;
        if (RANDOMIZER_RUNTIME_STATIC_MODE == 0
         && IsSpecialSpecies(candidate) != originalIsSpecial)
            continue;
        return candidate;
    }
#endif

    return originalSpecies;
}

enum Species RuntimeRandomizerStaticPresentationSpecies(
    enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_STATICS
    struct RuntimeStaticSource
    {
        u16 mapId;
        enum Species species;
    };
#define RUNTIME_STATIC_SOURCE(mapId, species) {mapId, species},
    static const struct RuntimeStaticSource sStaticSources[] =
    {
        RANDOMIZER_RUNTIME_STATIC_SOURCES(RUNTIME_STATIC_SOURCE)
        {0xFFFF, SPECIES_NONE},
    };
#undef RUNTIME_STATIC_SOURCE
    u16 mapId = ((u16)gSaveBlock1Ptr->location.mapGroup << 8)
              | gSaveBlock1Ptr->location.mapNum;
    u32 i;

    for (i = 0; sStaticSources[i].mapId != 0xFFFF; i++)
    {
        if (sStaticSources[i].mapId == mapId
         && sStaticSources[i].species == originalSpecies)
            return RuntimeRandomizerStaticSpecies(0, 0, originalSpecies);
    }
#endif

    return originalSpecies;
}

enum Species RuntimeRandomizerFossilSpecies(enum Species originalSpecies)
{
    switch (originalSpecies)
    {
    case SPECIES_OMANYTE:
    case SPECIES_KABUTO:
    case SPECIES_AERODACTYL:
    case SPECIES_LILEEP:
    case SPECIES_ANORITH:
    case SPECIES_SHIELDON:
    case SPECIES_CRANIDOS:
    case SPECIES_TIRTOUGA:
    case SPECIES_ARCHEN:
    case SPECIES_TYRUNT:
    case SPECIES_AMAURA:
    case SPECIES_DRACOZOLT:
    case SPECIES_ARCTOZOLT:
    case SPECIES_DRACOVISH:
    case SPECIES_ARCTOVISH:
        break;
    default:
        return originalSpecies;
    }

#if RANDOMIZER_RUNTIME_STATICS && RANDOMIZER_RUNTIME_FOSSIL_ONLY
    {
        static const enum Species sFossilSpecies[] =
        {
            SPECIES_OMANYTE,
            SPECIES_KABUTO,
            SPECIES_AERODACTYL,
            SPECIES_LILEEP,
            SPECIES_ANORITH,
            SPECIES_SHIELDON,
            SPECIES_CRANIDOS,
            SPECIES_TIRTOUGA,
            SPECIES_ARCHEN,
            SPECIES_TYRUNT,
            SPECIES_AMAURA,
            SPECIES_DRACOZOLT,
            SPECIES_ARCTOZOLT,
            SPECIES_DRACOVISH,
            SPECIES_ARCTOVISH,
        };
        u32 attempt;
        u32 start = RuntimeRandomizerHash(
            RUNTIME_DOMAIN_STATIC_SPECIES, 0xF05511u,
            originalSpecies, 0) % ARRAY_COUNT(sFossilSpecies);

        for (attempt = 0; attempt < ARRAY_COUNT(sFossilSpecies); attempt++)
        {
            enum Species candidate = sFossilSpecies[
                (start + attempt) % ARRAY_COUNT(sFossilSpecies)];

            if (candidate != originalSpecies && IsSpeciesEnabled(candidate))
                return candidate;
        }
        return originalSpecies;
    }
#else
    return RuntimeRandomizerStaticSpecies(1, 0, originalSpecies);
#endif
}

enum Species RuntimeRandomizerEggSpecies(u32 context,
                                         enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_EGGS
    u32 mapKey = ((u32)gSaveBlock1Ptr->location.mapGroup << 16)
               | gSaveBlock1Ptr->location.mapNum;

    return RuntimeRandomizerSpecies(
        RUNTIME_DOMAIN_EGG_SPECIES, mapKey, context, originalSpecies,
        FALSE, FALSE);
#else
    return originalSpecies;
#endif
}

enum Species RuntimeRandomizerTradeSpecies(u32 tradeId, bool32 offered,
                                           enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_TRADES
    return RuntimeRandomizerSpecies(
        RUNTIME_DOMAIN_TRADE_SPECIES, tradeId, offered, originalSpecies,
        FALSE, FALSE);
#else
    return originalSpecies;
#endif
}

#if RANDOMIZER_RUNTIME_RIVAL_CONTINUITY
static s32 GetRivalPlayerStarterSlot(u32 trainerId)
{
    if ((trainerId >= TRAINER_BRENDAN_ROUTE_103_MUDKIP
      && trainerId <= TRAINER_BRENDAN_ROUTE_119_MUDKIP)
     || (trainerId >= TRAINER_MAY_ROUTE_103_MUDKIP
      && trainerId <= TRAINER_MAY_ROUTE_119_MUDKIP)
     || trainerId == TRAINER_BRENDAN_RUSTBORO_MUDKIP
     || trainerId == TRAINER_MAY_RUSTBORO_MUDKIP
     || trainerId == TRAINER_BRENDAN_LILYCOVE_MUDKIP
     || trainerId == TRAINER_MAY_LILYCOVE_MUDKIP)
        return 2;

    if ((trainerId >= TRAINER_BRENDAN_ROUTE_103_TREECKO
      && trainerId <= TRAINER_BRENDAN_ROUTE_119_TREECKO)
     || (trainerId >= TRAINER_MAY_ROUTE_103_TREECKO
      && trainerId <= TRAINER_MAY_ROUTE_119_TREECKO)
     || trainerId == TRAINER_BRENDAN_RUSTBORO_TREECKO
     || trainerId == TRAINER_MAY_RUSTBORO_TREECKO
     || trainerId == TRAINER_BRENDAN_LILYCOVE_TREECKO
     || trainerId == TRAINER_MAY_LILYCOVE_TREECKO)
        return 0;

    if ((trainerId >= TRAINER_BRENDAN_ROUTE_103_TORCHIC
      && trainerId <= TRAINER_BRENDAN_ROUTE_119_TORCHIC)
     || (trainerId >= TRAINER_MAY_ROUTE_103_TORCHIC
      && trainerId <= TRAINER_MAY_ROUTE_119_TORCHIC)
     || trainerId == TRAINER_BRENDAN_RUSTBORO_TORCHIC
     || trainerId == TRAINER_MAY_RUSTBORO_TORCHIC
     || trainerId == TRAINER_BRENDAN_LILYCOVE_TORCHIC
     || trainerId == TRAINER_MAY_LILYCOVE_TORCHIC)
        return 1;

    return -1;
}

static enum Species GetRuntimeRivalStarter(u32 playerSlot, u32 level)
{
    enum Species species = GetStarterPokemon((playerSlot + 1) % 3);
    u32 stage;

    for (stage = 0; stage < 2; stage++)
    {
        const struct Evolution *evolutions = GetSpeciesEvolutions(species);
        u32 i;
        enum Species target = SPECIES_NONE;

        for (i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
        {
            if ((evolutions[i].method == EVO_LEVEL
              || evolutions[i].method == EVO_LEVEL_BATTLE_ONLY)
             && evolutions[i].param <= level)
            {
                target = evolutions[i].targetSpecies;
                break;
            }
        }
        if (target == SPECIES_NONE)
            break;
        species = target;
    }
    return species;
}
#endif

#if RANDOMIZER_RUNTIME_RIVAL_CONTINUITY
static enum Species GetFirstMegaForm(enum Species species)
{
    const u16 *forms = gSpeciesInfo[species].formSpeciesIdTable;
    u32 i;

    for (i = 0; forms != NULL && forms[i] != FORM_SPECIES_END; i++)
    {
        enum Species candidate = (enum Species)forms[i];

        if (candidate > SPECIES_NONE && candidate < NUM_SPECIES
         && gSpeciesInfo[candidate].isMegaEvolution)
            return candidate;
    }
    return SPECIES_NONE;
}
#endif

#if RANDOMIZER_RUNTIME_TRAINERS && RANDOMIZER_RUNTIME_TRAINER_TYPE_THEMES
#define RUNTIME_GYM_THEME_COUNT 8

static s32 GetRuntimeTrainerThemeGroup(u32 trainerId)
{
    struct RuntimeTrainerThemeGroup
    {
        u16 trainerId;
        u8 groupId;
    };
#define RUNTIME_TRAINER_THEME_GROUP(id, group) {id, group},
    static const struct RuntimeTrainerThemeGroup sTrainerThemeGroups[] =
    {
        RANDOMIZER_RUNTIME_TRAINER_THEME_GROUPS(RUNTIME_TRAINER_THEME_GROUP)
        {TRAINERS_COUNT, 0},
    };
#undef RUNTIME_TRAINER_THEME_GROUP
    u32 i;

    for (i = 0; sTrainerThemeGroups[i].trainerId != TRAINERS_COUNT; i++)
    {
        if (sTrainerThemeGroups[i].trainerId == trainerId)
            return sTrainerThemeGroups[i].groupId;
    }
    return -1;
}

static enum Type GetRuntimeTrainerTheme(u32 groupId)
{
    enum Type shuffledTypes[ARRAY_COUNT(sRegularTypes)];
    u32 groupClass = groupId < RUNTIME_GYM_THEME_COUNT ? 0 : 1;
    u32 themeIndex = groupClass == 0 ? groupId : groupId - RUNTIME_GYM_THEME_COUNT;
    u32 i;

    for (i = 0; i < ARRAY_COUNT(sRegularTypes); i++)
        shuffledTypes[i] = sRegularTypes[i];

    for (i = ARRAY_COUNT(sRegularTypes) - 1; i > 0; i--)
    {
        u32 swapIndex = RuntimeRandomizerHash(
            RUNTIME_DOMAIN_TRAINER_SPECIES, 0x7E000000u | groupClass,
            i, 0) % (i + 1);
        enum Type temporary = shuffledTypes[i];

        shuffledTypes[i] = shuffledTypes[swapIndex];
        shuffledTypes[swapIndex] = temporary;
    }
    return shuffledTypes[themeIndex];
}

#undef RUNTIME_GYM_THEME_COUNT
#endif

enum Species RuntimeRandomizerTrainerSpecies(u32 trainerId, u32 slot,
                                             u32 partySize, u32 level,
                                             enum Species originalSpecies)
{
#if RANDOMIZER_RUNTIME_RIVAL_CONTINUITY
    s32 playerSlot = GetRivalPlayerStarterSlot(trainerId);

    if (playerSlot >= 0 && slot + 1 == partySize)
    {
        enum Species starter = GetRuntimeRivalStarter(playerSlot, level);

        if (gSpeciesInfo[originalSpecies].isMegaEvolution)
        {
            enum Species mega = GetFirstMegaForm(starter);

            return mega == SPECIES_NONE ? originalSpecies : mega;
        }
        return starter;
    }
#endif

#if RANDOMIZER_RUNTIME_TRAINERS
    {
        u32 key1 = RANDOMIZER_RUNTIME_TRAINER_MODE == 0
                 ? originalSpecies : trainerId;
        u32 key2 = RANDOMIZER_RUNTIME_TRAINER_MODE == 0 ? 0 : slot;
        u32 attempt;
#if RANDOMIZER_RUNTIME_TRAINER_TYPE_THEMES
        s32 themeGroup = GetRuntimeTrainerThemeGroup(trainerId);
        enum Type theme = themeGroup < 0
                        ? TYPE_NONE
                        : GetRuntimeTrainerTheme(themeGroup);
#endif

        if (gSpeciesInfo[originalSpecies].isMegaEvolution)
            return originalSpecies;

        for (attempt = 0; attempt < NUM_SPECIES * 2; attempt++)
        {
            enum Species candidate = RuntimeRandomizerSpecies(
                RUNTIME_DOMAIN_TRAINER_SPECIES, key1, key2 + attempt,
                originalSpecies, RANDOMIZER_RUNTIME_TRAINER_ALLOW_SPECIAL,
                RANDOMIZER_RUNTIME_TRAINER_SIMILAR_BST
             && attempt < NUM_SPECIES);

#if RANDOMIZER_RUNTIME_TRAINER_TYPE_THEMES
            if (theme == TYPE_NONE)
                return candidate;
            if (GetSpeciesType(candidate, 0) == theme
             || GetSpeciesType(candidate, 1) == theme)
                return candidate;
#else
            return candidate;
#endif
        }
    }
#endif

    return originalSpecies;
}

static bool32 IsRuntimeItemCandidate(enum Item item)
{
    enum TMHMIndex machine;

    if (item <= ITEM_NONE || item >= ITEMS_COUNT)
        return FALSE;
    if (gItemsInfo[item].name == NULL || gItemsInfo[item].name[0] == EOS)
        return FALSE;
    if (gItemsInfo[item].importance || gItemsInfo[item].pocket == POCKET_KEY_ITEMS)
        return FALSE;
    if (!RANDOMIZER_RUNTIME_ALL_FOSSILS
     && gItemsInfo[item].sortType == ITEM_TYPE_FOSSIL)
        return FALSE;
    if (item >= ITEM_PARTY_RESTORER)
        return FALSE;

    machine = GetItemTMHMIndex(item);
    if (machine > NUM_TECHNICAL_MACHINES)
        return FALSE;
    return TRUE;
}

enum Item RuntimeRandomizerItem(enum Item originalItem)
{
#if RANDOMIZER_RUNTIME_ITEMS
    u32 attempt;

    if (!IsRuntimeItemCandidate(originalItem))
        return originalItem;

    for (attempt = 0; attempt < ITEMS_COUNT * 2; attempt++)
    {
        enum Item candidate = 1 + RuntimeRandomizerHash(
            RUNTIME_DOMAIN_FIELD_ITEM, originalItem, 0, attempt)
            % (ITEMS_COUNT - 1);

        if (candidate != originalItem && IsRuntimeItemCandidate(candidate))
            return candidate;
    }
#endif

    return originalItem;
}

enum Type RuntimeRandomizerSpeciesType(enum Species species, u32 slot,
                                       enum Type originalType)
{
#if RANDOMIZER_RUNTIME_POKEMON_TYPES
    enum Type type;

    if (species <= SPECIES_NONE || species >= NUM_SPECIES)
        return originalType;
    if (RANDOMIZER_RUNTIME_PROTECT_TYPES(species))
        return originalType;

    if (slot == 1 && gSpeciesInfo[species].types[0] == gSpeciesInfo[species].types[1])
        return RuntimeRandomizerSpeciesType(species, 0, originalType);

    type = sRegularTypes[RuntimeRandomizerHash(
        RUNTIME_DOMAIN_SPECIES_TYPE, species, slot, 0) % ARRAY_COUNT(sRegularTypes)];

    if (slot == 1)
    {
        enum Type firstType = RuntimeRandomizerSpeciesType(
            species, 0, gSpeciesInfo[species].types[0]);
        if (type == firstType)
        {
            u32 firstIndex;
            u32 index = RuntimeRandomizerHash(
                RUNTIME_DOMAIN_SPECIES_TYPE, species, slot, 1)
                % (ARRAY_COUNT(sRegularTypes) - 1);

            for (firstIndex = 0; sRegularTypes[firstIndex] != firstType; firstIndex++)
                ;
            if (index >= firstIndex)
                index++;
            type = sRegularTypes[index];
        }
    }

    return type;
#else
    return originalType;
#endif
}

static bool32 IsBannedRandomAbility(enum Ability ability)
{
    switch (ability)
    {
    case ABILITY_NONE:
    case ABILITY_SCHOOLING:
    case ABILITY_FORECAST:
    case ABILITY_STANCE_CHANGE:
    case ABILITY_SHIELDS_DOWN:
    case ABILITY_ZEN_MODE:
    case ABILITY_BATTLE_BOND:
    case ABILITY_POWER_CONSTRUCT:
    case ABILITY_HUNGER_SWITCH:
    case ABILITY_ZERO_TO_HERO:
    case ABILITY_MULTITYPE:
    case ABILITY_RKS_SYSTEM:
    case ABILITY_DISGUISE:
    case ABILITY_ICE_FACE:
    case ABILITY_GULP_MISSILE:
    case ABILITY_COMMANDER:
    case ABILITY_TERA_SHIFT:
    case ABILITY_TERA_SHELL:
    case ABILITY_TERAFORM_ZERO:
        return TRUE;
    default:
        return FALSE;
    }
}

#if RANDOMIZER_RUNTIME_ABILITIES
static enum Species GetRuntimeAbilityFamilyKey(enum Species species)
{
    u32 depth;
    enum Species familyKey = species;

    if (sRuntimeAbilityFamilyCache[species] != SPECIES_NONE)
        return sRuntimeAbilityFamilyCache[species];

    for (depth = 0; depth < NUM_SPECIES; depth++)
    {
        enum Species parent;
        enum Species bestParent = familyKey;

        for (parent = SPECIES_NONE + 1; parent < NUM_SPECIES; parent++)
        {
            if (RawSpeciesEvolvesTo(parent, familyKey) && parent < bestParent)
                bestParent = parent;
        }
        if (bestParent == familyKey)
            break;
        familyKey = bestParent;
    }

    sRuntimeAbilityFamilyCache[species] = familyKey;
    return familyKey;
}

static enum Ability GetRuntimeAbilityForSlot(enum Species familyKey, u32 slot)
{
    u32 attempt;

    for (attempt = 0; attempt < ABILITIES_COUNT * 2; attempt++)
    {
        enum Ability candidate = RuntimeRandomizerHash(
            RUNTIME_DOMAIN_SPECIES_ABILITY, familyKey, slot, attempt)
            % ABILITIES_COUNT;
        u32 previousSlot;
        bool32 duplicate = FALSE;

        if (IsBannedRandomAbility(candidate)
         || gAbilitiesInfo[candidate].name[0] == EOS)
            continue;

        for (previousSlot = 0; previousSlot < slot; previousSlot++)
        {
            if (GetRuntimeAbilityForSlot(familyKey, previousSlot) == candidate)
            {
                duplicate = TRUE;
                break;
            }
        }
        if (!duplicate)
            return candidate;
    }

    return ABILITY_NONE;
}
#endif

static bool32 IsBannedRandomMove(enum Move move)
{
    switch (move)
    {
    case MOVE_NONE:
    case MOVE_STRUGGLE:
    case MOVE_PIKA_PAPOW:
    case MOVE_VEEVEE_VOLLEY:
    case MOVE_BOUNCY_BUBBLE:
    case MOVE_BUZZY_BUZZ:
    case MOVE_SIZZLY_SLIDE:
    case MOVE_GLITZY_GLOW:
    case MOVE_BADDY_BAD:
    case MOVE_SAPPY_SEED:
    case MOVE_FREEZY_FROST:
    case MOVE_SPARKLY_SWIRL:
    case MOVE_SKETCH:
        return TRUE;
    default:
        return FALSE;
    }
}

static bool32 MoveAlreadyChosen(const struct LevelUpMove *moves, u32 count,
                                enum Move candidate)
{
    u32 i;

    for (i = 0; i < count; i++)
    {
        if (moves[i].move == candidate)
            return TRUE;
    }
    return FALSE;
}

static u32 CountSpeciesMovePool(enum Species species)
{
    const struct LevelUpMove *levelMoves = gSpeciesInfo[species].levelUpLearnset;
    const u16 *teachableMoves = gSpeciesInfo[species].teachableLearnset;
    const u16 *eggMoves = gSpeciesInfo[species].eggMoveLearnset;
    u32 count = 0;

    while (levelMoves != NULL && levelMoves->move != LEVEL_UP_MOVE_END)
    {
        count++;
        levelMoves++;
    }
    while (teachableMoves != NULL && *teachableMoves != MOVE_UNAVAILABLE)
    {
        count++;
        teachableMoves++;
    }
    while (eggMoves != NULL && *eggMoves != MOVE_UNAVAILABLE)
    {
        count++;
        eggMoves++;
    }
    return count;
}

static enum Move GetSpeciesMovePoolEntry(enum Species species, u32 index)
{
    const struct LevelUpMove *levelMoves = gSpeciesInfo[species].levelUpLearnset;
    const u16 *teachableMoves = gSpeciesInfo[species].teachableLearnset;
    const u16 *eggMoves = gSpeciesInfo[species].eggMoveLearnset;

    while (levelMoves != NULL && levelMoves->move != LEVEL_UP_MOVE_END)
    {
        if (index-- == 0)
            return levelMoves->move;
        levelMoves++;
    }
    while (teachableMoves != NULL && *teachableMoves != MOVE_UNAVAILABLE)
    {
        if (index-- == 0)
            return *teachableMoves;
        teachableMoves++;
    }
    while (eggMoves != NULL && *eggMoves != MOVE_UNAVAILABLE)
    {
        if (index-- == 0)
            return *eggMoves;
        eggMoves++;
    }
    return MOVE_NONE;
}

static enum Move RandomizedMove(enum Species species, u32 slot,
                                enum Move originalMove,
                                const struct LevelUpMove *chosen, u32 count)
{
    u32 attempt;
    u32 speciesPoolCount = RANDOMIZER_RUNTIME_MOVE_SPECIES_SPECIFIC
                         ? CountSpeciesMovePool(species)
                         : 0;

    for (attempt = 0; attempt < MOVES_COUNT * 2; attempt++)
    {
        u32 roll = RuntimeRandomizerHash(
            RUNTIME_DOMAIN_LEVEL_UP_MOVE, species, slot, attempt);
        enum Move candidate = speciesPoolCount == 0
                            ? 1 + roll % (MOVES_COUNT - 1)
                            : GetSpeciesMovePoolEntry(
                                species, roll % speciesPoolCount);

        if (IsBannedRandomMove(candidate) || MoveAlreadyChosen(chosen, count, candidate))
            continue;

        if (RANDOMIZER_RUNTIME_MOVE_SAME_TYPE_BIAS
         && RuntimeRandomizerHash(RUNTIME_DOMAIN_LEVEL_UP_MOVE,
                                  species, slot, attempt + MOVES_COUNT) % 2 != 0
         && GetMoveType(candidate) != GetSpeciesType(species, 0)
         && GetMoveType(candidate) != GetSpeciesType(species, 1))
            continue;

        return candidate;
    }

    return originalMove;
}

static bool32 RuntimeLearnsetContains(u32 count, enum Move move)
{
    return MoveAlreadyChosen(sRuntimeLevelUpLearnset, count, move);
}

static enum Move FindMoveOfType(enum Species species, u32 key, enum Type type)
{
    u32 attempt;

    for (attempt = 0; attempt < MOVES_COUNT * 2; attempt++)
    {
        enum Move move = 1 + RuntimeRandomizerHash(
            RUNTIME_DOMAIN_LEVEL_UP_MOVE, species, key, attempt)
            % (MOVES_COUNT - 1);

        if (!IsBannedRandomMove(move) && GetMoveType(move) == type)
            return move;
    }
    return MOVE_NONE;
}

static u32 AddEvolutionMoves(enum Species species, u32 count)
{
#if RANDOMIZER_RUNTIME_EVOLUTION_MOVES
    const struct Evolution *evolutions = gSpeciesInfo[species].evolutions;
    u32 i;

    for (i = 0; evolutions != NULL && evolutions[i].method != EVOLUTIONS_END; i++)
    {
        const struct EvolutionParam *params = evolutions[i].params;
        u32 j;

        for (j = 0; params != NULL && params[j].condition != CONDITIONS_END; j++)
        {
            enum Move move = MOVE_NONE;

            if (params[j].condition == IF_KNOWS_MOVE
             || params[j].condition == IF_USED_MOVE_X_TIMES)
                move = params[j].arg1;
            else if (params[j].condition == IF_KNOWS_MOVE_TYPE)
                move = FindMoveOfType(species, i * 16 + j, params[j].arg1);

            if (move != MOVE_NONE && !RuntimeLearnsetContains(count, move)
             && count < RUNTIME_LEVEL_UP_CAPACITY - 1)
            {
                sRuntimeLevelUpLearnset[count].move = move;
                sRuntimeLevelUpLearnset[count].level = 0;
                count++;
            }
        }
    }

    if (species == SPECIES_BASCULIN_WHITE_STRIPED
     && !RuntimeLearnsetContains(count, MOVE_TAKE_DOWN)
     && count < RUNTIME_LEVEL_UP_CAPACITY - 1)
    {
        sRuntimeLevelUpLearnset[count].move = MOVE_TAKE_DOWN;
        sRuntimeLevelUpLearnset[count].level = 0;
        count++;
    }
#endif

    return count;
}

enum Ability RuntimeRandomizerSpeciesAbility(enum Species species, u32 slot,
                                             enum Ability originalAbility)
{
#if RANDOMIZER_RUNTIME_ABILITIES
    enum Ability ability;
    enum Species familyKey;

    if (species <= SPECIES_NONE || species >= NUM_SPECIES)
        return originalAbility;
    if (slot >= NUM_ABILITY_SLOTS)
        return originalAbility;
    if (RANDOMIZER_RUNTIME_PROTECT_ABILITIES(species))
        return originalAbility;

    /* Evolution families retain one shared set of three abilities. */
    familyKey = GetRuntimeAbilityFamilyKey(species);
    ability = GetRuntimeAbilityForSlot(familyKey, slot);
    if (ability != ABILITY_NONE)
        return ability;
#endif

    return originalAbility;
}

u32 RuntimeRandomizerSpeciesStat(enum Species species, u32 stat,
                                 u32 originalStat)
{
#if RANDOMIZER_RUNTIME_POKEMON_BST
    u32 bst;
    u32 remaining;
    u32 minimum;
    u32 maximum;
    u32 values[NUM_STATS];
    u8 order[NUM_STATS];
    u32 i;

    if (species <= SPECIES_NONE || species >= NUM_SPECIES || stat >= NUM_STATS)
        return originalStat;
    if (RANDOMIZER_RUNTIME_PROTECT_STATS(species))
        return originalStat;
    if (gSpeciesInfo[species].isPrimalReversion
     || gSpeciesInfo[species].isUltraBurst
     || gSpeciesInfo[species].isGigantamax
     || gSpeciesInfo[species].isTeraForm
     || gSpeciesInfo[species].isTotem)
        return originalStat;

    bst = GetRuntimeTargetBst(species);
    minimum = max(1, (bst + 9) / 10);
    maximum = min(255, bst / 2);
    remaining = bst - minimum * NUM_STATS;

    for (i = 0; i < NUM_STATS; i++)
    {
        values[i] = minimum;
        order[i] = i;
    }

    for (i = NUM_STATS - 1; i > 0; i--)
    {
        u32 swapIndex = RuntimeRandomizerHash(
            RUNTIME_DOMAIN_SPECIES_STAT, species, NUM_STATS + i, 0) % (i + 1);
        u8 temp = order[i];

        order[i] = order[swapIndex];
        order[swapIndex] = temp;
    }

    for (i = 0; i < NUM_STATS; i++)
    {
        u32 slotsAfter = NUM_STATS - i - 1;
        u32 capacity = maximum - minimum;
        u32 remainingCapacity = slotsAfter * capacity;
        u32 minExtra = remaining > remainingCapacity
                     ? remaining - remainingCapacity
                     : 0;
        u32 maxExtra = min(capacity, remaining);
        u32 extra = i == NUM_STATS - 1
                  ? remaining
                  : minExtra + RuntimeRandomizerHash(
                        RUNTIME_DOMAIN_SPECIES_STAT, species, i, 1)
                        % (maxExtra - minExtra + 1);

        values[order[i]] += extra;
        remaining -= extra;
    }
    return values[stat];
#endif

    return originalStat;
}

enum Type RuntimeRandomizerMoveType(enum Move move, enum Type originalType)
{
#if RANDOMIZER_RUNTIME_MOVE_TYPES
    if (move > MOVE_NONE && move < MOVES_COUNT && move != MOVE_STRUGGLE)
        return sRegularTypes[RuntimeRandomizerHash(
            RUNTIME_DOMAIN_MOVE_TYPE, move, 0, 0) % ARRAY_COUNT(sRegularTypes)];
#endif

    return originalType;
}

const struct LevelUpMove *RuntimeRandomizerLevelUpLearnset(
    enum Species species, const struct LevelUpMove *originalLearnset)
{
#if RANDOMIZER_RUNTIME_MOVES || RANDOMIZER_RUNTIME_EVOLUTION_MOVES
    u32 i;

    for (i = 0; i < RUNTIME_LEVEL_UP_CAPACITY - 1
             && originalLearnset[i].move != LEVEL_UP_MOVE_END; i++)
    {
        sRuntimeLevelUpLearnset[i] = originalLearnset[i];
#if RANDOMIZER_RUNTIME_MOVES
        if (!RANDOMIZER_RUNTIME_PROTECT_MOVES(species))
        {
            sRuntimeLevelUpLearnset[i].move = RandomizedMove(
                species, i, originalLearnset[i].move, sRuntimeLevelUpLearnset, i);
        }
#endif
    }
#if RANDOMIZER_RUNTIME_EVOLUTION_MOVES
    if (!RANDOMIZER_RUNTIME_PROTECT_EVOLUTION_MOVES(species))
        i = AddEvolutionMoves(species, i);
#endif
    sRuntimeLevelUpLearnset[i].move = LEVEL_UP_MOVE_END;
    sRuntimeLevelUpLearnset[i].level = 0;
    return sRuntimeLevelUpLearnset;
#else
    return originalLearnset;
#endif
}

const u16 *RuntimeRandomizerTeachableLearnset(
    enum Species species, const u16 *originalLearnset)
{
#if RANDOMIZER_RUNTIME_TMS
    u32 i;

    if (RANDOMIZER_RUNTIME_PROTECT_TMS(species))
        return originalLearnset;

    if (sRuntimeTeachablePoolCount == 0)
    {
        u32 source;

        for (source = 1; source <= NUM_ALL_MACHINES; source++)
        {
            enum Move move = GetTMHMMoveId(source);
            u32 poolIndex;
            bool32 found = FALSE;

            for (poolIndex = 0; poolIndex < sRuntimeTeachablePoolCount; poolIndex++)
            {
                if (sRuntimeTeachablePool[poolIndex] == move)
                {
                    found = TRUE;
                    break;
                }
            }
            if (!found && !IsBannedRandomMove(move)
             && sRuntimeTeachablePoolCount < RUNTIME_TEACHABLE_CAPACITY)
                sRuntimeTeachablePool[sRuntimeTeachablePoolCount++] = move;
        }

        for (source = 0; gTutorMoves[source] != MOVE_UNAVAILABLE; source++)
        {
            enum Move move = gTutorMoves[source];
            u32 poolIndex;
            bool32 found = FALSE;

            for (poolIndex = 0; poolIndex < sRuntimeTeachablePoolCount; poolIndex++)
            {
                if (sRuntimeTeachablePool[poolIndex] == move)
                {
                    found = TRUE;
                    break;
                }
            }
            if (!found && !IsBannedRandomMove(move)
             && sRuntimeTeachablePoolCount < RUNTIME_TEACHABLE_CAPACITY)
                sRuntimeTeachablePool[sRuntimeTeachablePoolCount++] = move;
        }
    }

    for (i = 0; i < RUNTIME_TEACHABLE_CAPACITY - 1
             && originalLearnset[i] != MOVE_UNAVAILABLE; i++)
    {
        enum Move candidate = MOVE_NONE;
        u32 attempt;

        for (attempt = 0; attempt < sRuntimeTeachablePoolCount * 2; attempt++)
        {
            u32 j;
            bool32 duplicate = FALSE;

            candidate = sRuntimeTeachablePool[RuntimeRandomizerHash(
                RUNTIME_DOMAIN_TM_COMPATIBILITY, species, i, attempt)
                % sRuntimeTeachablePoolCount];
            for (j = 0; j < i; j++)
            {
                if (sRuntimeTeachableLearnset[j] == candidate)
                {
                    duplicate = TRUE;
                    break;
                }
            }
            if (duplicate || IsBannedRandomMove(candidate))
                continue;
            if (RuntimeRandomizerHash(
                    RUNTIME_DOMAIN_TM_COMPATIBILITY, species, i,
                    attempt + sRuntimeTeachablePoolCount) % 2 != 0
             && GetMoveType(candidate) != GetSpeciesType(species, 0)
             && GetMoveType(candidate) != GetSpeciesType(species, 1))
                continue;
            break;
        }
        if (candidate == MOVE_NONE || attempt == sRuntimeTeachablePoolCount * 2)
            candidate = originalLearnset[i];
        sRuntimeTeachableLearnset[i] = candidate;
    }
    sRuntimeTeachableLearnset[i] = MOVE_UNAVAILABLE;
    return sRuntimeTeachableLearnset;
#else
    return originalLearnset;
#endif
}

const struct Evolution *RuntimeRandomizerEvolutions(
    enum Species species, const struct Evolution *originalEvolutions)
{
#if RANDOMIZER_RUNTIME_EVOLUTIONS
    u32 i;
    u32 sourceBst = GetRuntimeTargetBst(species);

    if (RANDOMIZER_RUNTIME_PROTECT_EVOLUTIONS(species))
        return originalEvolutions;

    for (i = 0; i < RUNTIME_EVOLUTION_CAPACITY - 1
             && originalEvolutions[i].method != EVOLUTIONS_END; i++)
    {
        u32 attempt;

        sRuntimeEvolutions[i] = originalEvolutions[i];
        for (attempt = 0; attempt < NUM_SPECIES * 2; attempt++)
        {
            enum Species candidate = RuntimeRandomizerSpecies(
                RUNTIME_DOMAIN_EVOLUTION, species, i + attempt,
                originalEvolutions[i].targetSpecies, FALSE, TRUE);

            if (GetRuntimeTargetBst(candidate) > sourceBst)
            {
                sRuntimeEvolutions[i].targetSpecies = candidate;
                break;
            }
        }
    }
    sRuntimeEvolutions[i].method = EVOLUTIONS_END;
    sRuntimeEvolutions[i].param = 0;
    sRuntimeEvolutions[i].targetSpecies = SPECIES_NONE;
    sRuntimeEvolutions[i].params = NULL;
    return sRuntimeEvolutions;
#else
    return originalEvolutions;
#endif
}
