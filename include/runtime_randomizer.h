#ifndef GUARD_RUNTIME_RANDOMIZER_H
#define GUARD_RUNTIME_RANDOMIZER_H

#include "global.h"
#include "constants/abilities.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/species.h"

struct Evolution;
struct LevelUpMove;

enum RuntimeRandomizerDomain
{
    RUNTIME_DOMAIN_STARTER = 1,
    RUNTIME_DOMAIN_SPECIES_TYPE,
    RUNTIME_DOMAIN_SPECIES_ABILITY,
    RUNTIME_DOMAIN_SPECIES_STAT,
    RUNTIME_DOMAIN_EVOLUTION,
    RUNTIME_DOMAIN_MOVE_TYPE,
    RUNTIME_DOMAIN_LEVEL_UP_MOVE,
    RUNTIME_DOMAIN_TM_COMPATIBILITY,
    RUNTIME_DOMAIN_WILD_SPECIES,
    RUNTIME_DOMAIN_STATIC_SPECIES,
    RUNTIME_DOMAIN_EGG_SPECIES,
    RUNTIME_DOMAIN_TRADE_SPECIES,
    RUNTIME_DOMAIN_TRAINER_SPECIES,
    RUNTIME_DOMAIN_FIELD_ITEM,
};

u32 RuntimeRandomizerGetSaveSeed(void);
u32 RuntimeRandomizerHash(u32 domain, u32 key1, u32 key2, u32 key3);
enum Species RuntimeRandomizerSpecies(u32 domain, u32 key1, u32 key2,
                                      enum Species originalSpecies,
                                      bool32 allowSpecial, bool32 similarBst);
enum Species RuntimeRandomizerStarter(u32 slot, enum Species originalSpecies);
enum Species RuntimeRandomizerWildSpecies(u32 area, u32 slot,
                                          enum Species originalSpecies);
enum Species RuntimeRandomizerStaticSpecies(u32 context, u32 slot,
                                            enum Species originalSpecies);
enum Species RuntimeRandomizerStaticPresentationSpecies(
    enum Species originalSpecies);
enum Species RuntimeRandomizerFossilSpecies(enum Species originalSpecies);
enum Species RuntimeRandomizerEggSpecies(u32 context,
                                         enum Species originalSpecies);
enum Species RuntimeRandomizerTradeSpecies(u32 tradeId, bool32 offered,
                                           enum Species originalSpecies);
enum Species RuntimeRandomizerTrainerSpecies(u32 trainerId, u32 slot,
                                             u32 partySize, u32 level,
                                             enum Species originalSpecies);
enum Item RuntimeRandomizerItem(enum Item originalItem);
enum Type RuntimeRandomizerSpeciesType(enum Species species, u32 slot,
                                       enum Type originalType);
enum Ability RuntimeRandomizerSpeciesAbility(enum Species species, u32 slot,
                                             enum Ability originalAbility);
u32 RuntimeRandomizerSpeciesStat(enum Species species, u32 stat,
                                 u32 originalStat);
enum Type RuntimeRandomizerMoveType(enum Move move, enum Type originalType);
const struct LevelUpMove *RuntimeRandomizerLevelUpLearnset(
    enum Species species, const struct LevelUpMove *originalLearnset);
const u16 *RuntimeRandomizerTeachableLearnset(
    enum Species species, const u16 *originalLearnset);
const struct Evolution *RuntimeRandomizerEvolutions(
    enum Species species, const struct Evolution *originalEvolutions);

#endif // GUARD_RUNTIME_RANDOMIZER_H
