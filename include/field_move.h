#ifndef GUARD_FIELD_MOVE_H
#define GUARD_FIELD_MOVE_H

#include "global.h"
#include "randomizer_game_options.h"
#include "constants/field_move.h"

struct FieldMoveInfo
{
    bool32 (*fieldMoveFunc)(void);
    bool32 (*isUnlockedFunc)(void);
    u16 moveID;
    u8 partyMsgID;
};

extern const struct FieldMoveInfo gFieldMoveInfo[];

static inline bool32 SetUpFieldMove(enum FieldMove fieldMove)
{
    return gFieldMoveInfo[fieldMove].fieldMoveFunc();
}

static inline bool32 IsFieldMoveUnlocked(enum FieldMove fieldMove)
{
    // RANDOMIZER GAME OPTIONS: HM PROGRESSION BYPASS
#if RANDOMIZER_HM_FREE_FIELD_MOVES
    // Rock Climb is disabled by Expansion's normal feature config rather
    // than a Hoenn badge. The combined HM-free option explicitly enables it.
    if (fieldMove == FIELD_MOVE_ROCK_CLIMB)
        return TRUE;
#endif

#if RANDOMIZER_HM_PROGRESSION_BYPASS
    switch (fieldMove)
    {
    case FIELD_MOVE_CUT:
    case FIELD_MOVE_FLASH:
    case FIELD_MOVE_ROCK_SMASH:
    case FIELD_MOVE_STRENGTH:
    case FIELD_MOVE_SURF:
    case FIELD_MOVE_FLY:
    case FIELD_MOVE_DIVE:
    case FIELD_MOVE_WATERFALL:
    case FIELD_MOVE_ROCK_CLIMB:
    case FIELD_MOVE_DEFOG:
        return TRUE;
    default:
        break;
    }
#endif

    return gFieldMoveInfo[fieldMove].isUnlockedFunc();
}

static inline u32 FieldMove_GetMoveId(enum FieldMove fieldMove)
{
    return gFieldMoveInfo[fieldMove].moveID;
}

static inline u32 FieldMove_GetPartyMsgID(enum FieldMove fieldMove)
{
    return gFieldMoveInfo[fieldMove].partyMsgID;
}

#endif //GUARD_FIELD_MOVE_H
