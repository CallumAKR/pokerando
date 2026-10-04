#include "global.h"
#include "clock.h"
#include "new_game.h"
#include "random.h"
#include "pokemon.h"
#include "roamer.h"
#include "pokemon_size_record.h"
#include "script.h"
#include "lottery_corner.h"
#include "play_time.h"
#include "mauville_old_man.h"
#include "match_call.h"
#include "lilycove_lady.h"
#include "load_save.h"
#include "pokeblock.h"
#include "dewford_trend.h"
#include "berry.h"
#include "rtc.h"
#include "easy_chat.h"
#include "event_data.h"
#include "money.h"
#include "trainer_hill.h"
#include "trainer_tower.h"
#include "tv.h"
#include "coins.h"
#include "text.h"
#include "overworld.h"
#include "mail.h"
#include "battle_records.h"
#include "item.h"
#include "pokedex.h"
#include "apprentice.h"
#include "frontier_util.h"
#include "save.h"
#include "link_rfu.h"
#include "main.h"
#include "contest.h"
#include "item_menu.h"
#include "pokemon_storage_system.h"
#include "pokemon_jump.h"
#include "decoration_inventory.h"
#include "secret_base.h"
#include "string_util.h"
#include "player_pc.h"
#include "field_specials.h"
#include "berry_powder.h"
#include "mystery_gift.h"
#include "union_room_chat.h"
#include "constants/map_groups.h"
#include "constants/items.h"
#include "difficulty.h"
#include "follower_npc.h"
#include "randomizer_game_options.h"

extern const u8 EventScript_ResetAllMapFlags[];
extern const u8 EventScript_ResetAllMapFlagsFrlg[];

static void ClearFrontierRecord(void);
static void WarpToTruck(void);
static void ResetMiniGamesRecords(void);
static void ResetItemFlags(void);
static void ResetDexNav(void);
static void GiveOneOffCustomParty(void);

EWRAM_DATA bool8 gDifferentSaveFile = FALSE;
EWRAM_DATA bool8 gEnableContestDebugging = FALSE;

static const struct ContestWinner sContestWinnerPicDummy =
{
    .monName = _(""),
    .trainerName = _(""),
};

struct OneOffPartyMon
{
    enum Species species;
    enum Ability ability;
    enum Item item;
    u8 nature;
    u8 hpEv;
    u8 attackEv;
    u8 speedEv;
    u8 spAttackEv;
};

static const struct OneOffPartyMon sOneOffParty[PARTY_SIZE] =
{
    {SPECIES_GOLETT,     ABILITY_IRON_FIST,    ITEM_PUNCHING_GLOVE, NATURE_ADAMANT, 252, 252,   4,   0},
    {SPECIES_KLEAVOR,    ABILITY_SHARPNESS,    ITEM_RAZOR_CLAW,     NATURE_JOLLY,     4, 252, 252,   0},
    {SPECIES_TYRUNT,     ABILITY_STRONG_JAW,   ITEM_RAZOR_FANG,     NATURE_ADAMANT,   4, 252, 252,   0},
    {SPECIES_MINCCINO,   ABILITY_SKILL_LINK,   ITEM_KINGS_ROCK,     NATURE_JOLLY,     4, 252, 252,   0},
    {SPECIES_CLAUNCHER,  ABILITY_MEGA_LAUNCHER, ITEM_WISE_GLASSES, NATURE_TIMID,     4,   0, 252, 252},
    {SPECIES_TOXTRICITY, ABILITY_PUNK_ROCK,    ITEM_METRONOME,      NATURE_MODEST,  252,   0,   4, 252},
};

void SetTrainerId(u32 trainerId, u8 *dst)
{
    dst[0] = trainerId;
    dst[1] = trainerId >> 8;
    dst[2] = trainerId >> 16;
    dst[3] = trainerId >> 24;
}

u32 GetTrainerId(u8 *trainerId)
{
    return (trainerId[3] << 24) | (trainerId[2] << 16) | (trainerId[1] << 8) | (trainerId[0]);
}

void CopyTrainerId(u8 *dst, u8 *src)
{
    s32 i;
    for (i = 0; i < TRAINER_ID_LENGTH; i++)
        dst[i] = src[i];
}

static void InitPlayerTrainerId(void)
{
    u32 trainerId = (Random() << 16) | GetGeneratedTrainerIdLower();
    SetTrainerId(trainerId, gSaveBlock2Ptr->playerTrainerId);
}

static void GiveOneOffCustomParty(void)
{
    u32 i;

    ZeroPlayerPartyMons();
    gPartiesCount[B_TRAINER_PLAYER] = PARTY_SIZE;

    for (i = 0; i < PARTY_SIZE; i++)
    {
        struct Pokemon *mon = &gParties[B_TRAINER_PLAYER][i];
        const struct OneOffPartyMon *preset = &sOneOffParty[i];
        u8 abilityNum;
        u8 zero = 0;

        // Personality modulo 25 determines nature, so the nature constant itself
        // is a deterministic personality with the requested nature.
        CreateMonWithIVs(mon, preset->species, 5, preset->nature, OTID_STRUCT_PLAYER_ID, MAX_PER_STAT_IVS);
        GiveMonInitialMoveset(mon);

        SetMonData(mon, MON_DATA_HELD_ITEM, &preset->item);
        SetMonData(mon, MON_DATA_HP_EV, &preset->hpEv);
        SetMonData(mon, MON_DATA_ATK_EV, &preset->attackEv);
        SetMonData(mon, MON_DATA_DEF_EV, &zero);
        SetMonData(mon, MON_DATA_SPEED_EV, &preset->speedEv);
        SetMonData(mon, MON_DATA_SPATK_EV, &preset->spAttackEv);
        SetMonData(mon, MON_DATA_SPDEF_EV, &zero);

        // Use the exact requested canonical ability when it exists in one of
        // the species' three ability slots.
        for (abilityNum = 0; abilityNum < NUM_ABILITY_SLOTS; abilityNum++)
        {
            if (GetAbilityBySpecies(preset->species, abilityNum) == preset->ability)
            {
                SetMonData(mon, MON_DATA_ABILITY_NUM, &abilityNum);
                break;
            }
        }

        CalculateMonStats(mon);
    }
}

// L=A isnt set here for some reason.
static void SetDefaultOptions(void)
{
    gSaveBlock2Ptr->optionsTextSpeed = OPTIONS_TEXT_SPEED_MID;
    gSaveBlock2Ptr->optionsWindowFrameType = 0;
    gSaveBlock2Ptr->optionsSound = OPTIONS_SOUND_MONO;
    gSaveBlock2Ptr->optionsBattleStyle = OPTIONS_BATTLE_STYLE_SHIFT;
    gSaveBlock2Ptr->optionsBattleSceneOff = FALSE;
    gSaveBlock2Ptr->regionMapZoom = FALSE;
}

static void ClearPokedexFlags(void)
{
    gUnusedPokedexU8 = 0;
    memset(&gSaveBlock1Ptr->dexCaught, 0, sizeof(gSaveBlock1Ptr->dexCaught));
    memset(&gSaveBlock1Ptr->dexSeen, 0, sizeof(gSaveBlock1Ptr->dexSeen));
}

void ClearAllContestWinnerPics(void)
{
    s32 i;

    ClearContestWinnerPicsInContestHall();

    for (i = MUSEUM_CONTEST_WINNERS_START; i < NUM_CONTEST_WINNERS; i++)
        gSaveBlock1Ptr->contestWinners[i] = sContestWinnerPicDummy;
}

static void ClearFrontierRecord(void)
{
    CpuFill32(0, &gSaveBlock2Ptr->frontier, sizeof(gSaveBlock2Ptr->frontier));
    gSaveBlock2Ptr->frontier.opponentNames[0][0] = EOS;
    gSaveBlock2Ptr->frontier.opponentNames[1][0] = EOS;
}

static void WarpToTruck(void)
{
    if (IS_FRLG)
        SetWarpDestination(MAP_GROUP(MAP_PALLET_TOWN_PLAYERS_HOUSE_2F), MAP_NUM(MAP_PALLET_TOWN_PLAYERS_HOUSE_2F), WARP_ID_NONE, 6, 6);
    else
        SetWarpDestination(MAP_GROUP(MAP_INSIDE_OF_TRUCK), MAP_NUM(MAP_INSIDE_OF_TRUCK), WARP_ID_NONE, -1, -1);
    WarpIntoMap();
}

void Sav2_ClearSetDefault(void)
{
    ClearSav2();
    SetDefaultOptions();
}

void ResetMenuAndMonGlobals(void)
{
    gDifferentSaveFile = FALSE;
    ResetPokedexScrollPositions();
    ZeroPlayerPartyMons();
    ZeroEnemyPartyMons();
    ResetBagScrollPositions();
    ResetPokeblockScrollPositions();
}

void NewGameInitData(void)
{
#if IS_FRLG
    u8 rivalName[PLAYER_NAME_LENGTH + 1];
#endif
    if (gSaveFileStatus == SAVE_STATUS_EMPTY || gSaveFileStatus == SAVE_STATUS_CORRUPT)
        RtcReset();

#if IS_FRLG
    StringCopy(rivalName, gSaveBlock1Ptr->rivalName);
#endif
    gDifferentSaveFile = TRUE;
    gSaveBlock2Ptr->encryptionKey = 0;
    ZeroPlayerPartyMons();
    ZeroEnemyPartyMons();
    ResetPokedex();
    ClearFrontierRecord();
    ClearSav1();
    ClearSav3();
    ClearAllMail();
    gSaveBlock2Ptr->specialSaveWarpFlags = 0;
    gSaveBlock2Ptr->gcnLinkFlags = 0;
    InitPlayerTrainerId();
    PlayTimeCounter_Reset();
    ClearPokedexFlags();
    InitEventData();
    ClearTVShowData();
    ResetGabbyAndTy();
    ClearSecretBases();
    ClearBerryTrees();
    SetMoney(&gSaveBlock1Ptr->money, 3000);
    SetCoins(0);
    ResetLinkContestBoolean();
    ResetGameStats();
    ClearAllContestWinnerPics();
    ClearPlayerLinkBattleRecords();
    InitSeedotSizeRecord();
    InitLotadSizeRecord();
    gPartiesCount[B_TRAINER_PLAYER] = 0;
    ZeroPlayerPartyMons();
    ResetPokemonStorageSystem();
    DeactivateAllRoamers();
    gSaveBlock1Ptr->registeredItem = ITEM_NONE;
    ClearBag();
#if RANDOMIZER_PARTY_HEAL
    AddBagItem(ITEM_PARTY_RESTORER, 1);
#endif
#if RANDOMIZER_PERMA_REPEL
    AddBagItem(ITEM_PERMA_REPEL, 1);
#endif
#if RANDOMIZER_TIME_TURNER
    AddBagItem(ITEM_TIME_TURNER, 1);
#endif
#if RANDOMIZER_WEATHER_SETTER
    AddBagItem(ITEM_WEATHER_SETTER, 1);
#endif
#if RANDOMIZER_HM_FREE_FIELD_MOVES
    AddBagItem(ITEM_FLY_TOOL, 1);
    AddBagItem(ITEM_FLASH_TOOL, 1);
    AddBagItem(ITEM_DIG_TOOL, 1);
    AddBagItem(ITEM_TELEPORT_TOOL, 1);
#endif
    NewGameInitPCItems();
    ClearPokeblocks();
    ClearDecorationInventories();
    InitEasyChatPhrases();
    SetMauvilleOldMan();
    InitDewfordTrend();
    ResetFanClub();
    ResetLotteryCorner();
    UpdateDailySeed();
    WarpToTruck();
    if (IS_FRLG)
        RunScriptImmediately(EventScript_ResetAllMapFlagsFrlg);
    else
        RunScriptImmediately(EventScript_ResetAllMapFlags);
#if RANDOMIZER_SKIP_INTRO
    if (!IS_FRLG)
    {
        FlagSet(FLAG_SET_WALL_CLOCK);
        InitTimeBasedEvents();
    }
#endif
#if IS_FRLG
    StringCopy(gSaveBlock1Ptr->rivalName, rivalName);
#endif
    ResetMiniGamesRecords();
    InitUnionRoomChatRegisteredTexts();
    InitLilycoveLady();
    ResetAllApprenticeData();
    ClearRankingHallRecords();
    InitMatchCallCounters();
    ClearMysteryGift();
    WipeTrainerNameRecords();
    ResetTrainerHillResults();
    ResetTrainerTowerResults();
    ResetContestLinkResults();
    SetCurrentDifficultyLevel(DIFFICULTY_NORMAL);
    ResetItemFlags();
    ResetDexNav();
    ClearFollowerNPCData();

    // One-off run preset: starts every new save with the requested six-mon team.
    GiveOneOffCustomParty();
}

static void ResetMiniGamesRecords(void)
{
    CpuFill16(0, &gSaveBlock2Ptr->berryCrush, sizeof(struct BerryCrush));
    ResetPokemonJumpRecords();
    CpuFill16(0, &gSaveBlock2Ptr->berryPick, sizeof(struct BerryPickingResults));
}

static void ResetItemFlags(void)
{
#if OW_SHOW_ITEM_DESCRIPTIONS == OW_ITEM_DESCRIPTIONS_FIRST_TIME
    memset(&gSaveBlock3Ptr->itemFlags, 0, sizeof(gSaveBlock3Ptr->itemFlags));
#endif
}

static void ResetDexNav(void)
{
#if USE_DEXNAV_SEARCH_LEVELS == TRUE
    memset(gSaveBlock3Ptr->dexNavSearchLevels, 0, sizeof(gSaveBlock3Ptr->dexNavSearchLevels));
#endif
    gSaveBlock3Ptr->dexNavChain = 0;
}
