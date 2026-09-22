LilycoveCity_DepartmentStore_4F_MapScripts::
	.byte 0

LilycoveCity_DepartmentStore_4F_EventScript_Gentleman::
	msgbox LilycoveCity_DepartmentStore_4F_Text_AttackOrDefenseTM, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_4F_EventScript_Woman::
	msgbox LilycoveCity_DepartmentStore_4F_Text_FiftyDifferentTMs, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_4F_EventScript_Youngster::
	msgbox LilycoveCity_DepartmentStore_4F_Text_PokemonOnlyHaveFourMoves, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_4F_EventScript_ClerkLeft::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	pokemart LilycoveCity_DepartmentStore_4F_Pokemart_AttackTMs
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LilycoveCity_DepartmentStore_4F_Pokemart_AttackTMs:








































	.2byte ITEM_TM01

	.2byte ITEM_TM02

	.2byte ITEM_TM03

	.2byte ITEM_TM04

	.2byte ITEM_TM05

	.2byte ITEM_TM06

	.2byte ITEM_TM07

	.2byte ITEM_TM08

	.2byte ITEM_TM09

	.2byte ITEM_TM_WORK_UP

	.2byte ITEM_TM11

	.2byte ITEM_TM12

	.2byte ITEM_TM13

	.2byte ITEM_TM14

	.2byte ITEM_TM15

	.2byte ITEM_TM16

	.2byte ITEM_TM17

	.2byte ITEM_TM18

	.2byte ITEM_TM19

	.2byte ITEM_TM20

	.2byte ITEM_TM_DAZZLING_GLEAM

	.2byte ITEM_TM22

	.2byte ITEM_TM23

	.2byte ITEM_TM24

	.2byte ITEM_TM25

	.2byte ITEM_TM26

	.2byte ITEM_TM_LOW_SWEEP

	.2byte ITEM_TM28

	.2byte ITEM_TM29

	.2byte ITEM_TM30

	.2byte ITEM_TM31

	.2byte ITEM_TM32

	.2byte ITEM_TM33

	.2byte ITEM_TM34

	.2byte ITEM_TM35

	.2byte ITEM_TM36

	.2byte ITEM_TM37

	.2byte ITEM_TM38

	.2byte ITEM_TM39

	.2byte ITEM_TM40

	.2byte ITEM_TM41

	.2byte ITEM_TM42

	.2byte ITEM_TM_VOLT_SWITCH

	.2byte ITEM_TM44

	.2byte ITEM_TM45

	.2byte ITEM_TM46

	.2byte ITEM_TM47

	.2byte ITEM_TM48

	.2byte ITEM_TM_SCALD

	.2byte ITEM_TM50

	.2byte ITEM_NONE
LilycoveCity_DepartmentStore_4F_EventScript_ClerkRight::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	pokemart LilycoveCity_DepartmentStore_4F_Pokemart_DefenseTMs
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LilycoveCity_DepartmentStore_4F_Pokemart_DefenseTMs:








































	.2byte ITEM_TM_ROOST

	.2byte ITEM_TM_FOCUS_BLAST

	.2byte ITEM_TM_ENERGY_BALL

	.2byte ITEM_TM_FALSE_SWIPE

	.2byte ITEM_TM_BRINE

	.2byte ITEM_TM_FLING

	.2byte ITEM_TM_CHARGE_BEAM

	.2byte ITEM_TM_ENDURE

	.2byte ITEM_TM_DRAGON_PULSE

	.2byte ITEM_TM_DRAIN_PUNCH

	.2byte ITEM_TM_WILL_O_WISP

	.2byte ITEM_TM_BUG_BUZZ

	.2byte ITEM_TM_NASTY_PLOT

	.2byte ITEM_TM_EXPLOSION

	.2byte ITEM_TM_SHADOW_CLAW

	.2byte ITEM_TM_PAYBACK

	.2byte ITEM_TM_RECYCLE

	.2byte ITEM_TM_GIGA_IMPACT

	.2byte ITEM_TM_ROCK_POLISH

	.2byte ITEM_TM_FLASH

	.2byte ITEM_TM_STONE_EDGE

	.2byte ITEM_TM_AVALANCHE

	.2byte ITEM_TM_THUNDER_WAVE

	.2byte ITEM_TM_GYRO_BALL

	.2byte ITEM_TM_SWORDS_DANCE

	.2byte ITEM_TM_STEALTH_ROCK

	.2byte ITEM_TM_PSYCH_UP

	.2byte ITEM_TM_SNARL

	.2byte ITEM_TM_DARK_PULSE

	.2byte ITEM_TM_ROCK_SLIDE

	.2byte ITEM_TM_X_SCISSOR

	.2byte ITEM_TM_SLEEP_TALK

	.2byte ITEM_TM_BULLDOZE

	.2byte ITEM_TM_POISON_JAB

	.2byte ITEM_TM_DREAM_EATER

	.2byte ITEM_TM_GRASS_KNOT

	.2byte ITEM_TM_SWAGGER

	.2byte ITEM_TM_PLUCK

	.2byte ITEM_TM_U_TURN

	.2byte ITEM_TM_SUBSTITUTE

	.2byte ITEM_TM_FLASH_CANNON

	.2byte ITEM_TM_TRICK_ROOM

	.2byte ITEM_TM_CUT

	.2byte ITEM_TM_FLY

	.2byte ITEM_TM_SURF

	.2byte ITEM_TM_STRENGTH

	.2byte ITEM_TM_DEFOG

	.2byte ITEM_TM_ROCK_SMASH

	.2byte ITEM_TM_WATERFALL

	.2byte ITEM_TM_ROCK_CLIMB

	.2byte ITEM_NONE
LilycoveCity_DepartmentStore_4F_Text_AttackOrDefenseTM:
	.string "Hmm…\p"
	.string "An attacking move…\n"
	.string "Or a defensive move…\p"
	.string "It's no easy matter to decide which TM\n"
	.string "moves should be taught to POKéMON…$"

LilycoveCity_DepartmentStore_4F_Text_FiftyDifferentTMs:
	.string "There are so many different kinds of\n"
	.string "TM moves.\p"
	.string "A catalog I read said there are fifty\n"
	.string "different kinds.$"

LilycoveCity_DepartmentStore_4F_Text_PokemonOnlyHaveFourMoves:
	.string "I'd like to get all the different TMs,\n"
	.string "but a POKéMON learns only four moves.$"

