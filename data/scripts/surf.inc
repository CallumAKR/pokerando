EventScript_UseSurf::
        lockall

        checkfieldmove FIELD_MOVE_SURF, TRUE
        goto_if_eq VAR_RESULT, PARTY_SIZE, EventScript_EndUseSurf

        @ No Pokémon needs to know Surf.
        setfieldeffectargument 0, 0

        dofieldeffect FLDEFF_USE_SURF

EventScript_ReleaseUseSurf::
        releaseall

EventScript_EndUseSurf::
        end


EventScript_CurrentTooFast::
        lockall
        playse SE_SELECT
        msgbox Text_CurrentTooFast
        releaseall
        end
