LilycoveCity_DepartmentStore_2F_MapScripts::
	.byte 0

LilycoveCity_DepartmentStore_2F_EventScript_Cook::
	msgbox LilycoveCity_DepartmentStore_2F_Text_LearnToUseItemsProperly, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_2F_EventScript_PokefanF::
	msgbox LilycoveCity_DepartmentStore_2F_Text_GoodGiftForHusband, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_2F_EventScript_Sailor::
	msgbox LilycoveCity_DepartmentStore_2F_Text_StockUpOnItems, MSGBOX_NPC
	end

LilycoveCity_DepartmentStore_2F_EventScript_ClerkLeft::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	pokemart LilycoveCity_DepartmentStore_2F_Pokemart1
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LilycoveCity_DepartmentStore_2F_Pokemart1:







































	.2byte ITEM_POKE_BALL

	.2byte ITEM_GREAT_BALL

	.2byte ITEM_ULTRA_BALL

	.2byte ITEM_ESCAPE_ROPE

	.2byte ITEM_FULL_HEAL

	.2byte ITEM_ANTIDOTE

	.2byte ITEM_PARALYZE_HEAL

	.2byte ITEM_BURN_HEAL

	.2byte ITEM_ICE_HEAL

	.2byte ITEM_AWAKENING

	.2byte ITEM_FLUFFY_TAIL

	.2byte ITEM_POTION

	.2byte ITEM_SUPER_POTION

	.2byte ITEM_HYPER_POTION

	.2byte ITEM_MAX_POTION

	.2byte ITEM_REVIVE

	.2byte ITEM_REPEL

	.2byte ITEM_SUPER_REPEL

	.2byte ITEM_MAX_REPEL

	.2byte ITEM_WAVE_MAIL

	.2byte ITEM_MECH_MAIL

	.2byte ITEM_ADAMANT_CRYSTAL

	.2byte ITEM_ARMORITE_ORE

	.2byte ITEM_AUSPICIOUS_ARMOR

	.2byte ITEM_BERRY_SWEET

	.2byte ITEM_BLACK_AUGURITE

	.2byte ITEM_CHIPPED_POT

	.2byte ITEM_CLOVER_SWEET

	.2byte ITEM_CRACKED_POT

	.2byte ITEM_DAWN_STONE

	.2byte ITEM_DEEP_SEA_SCALE

	.2byte ITEM_DEEP_SEA_TOOTH

	.2byte ITEM_DRAGON_SCALE

	.2byte ITEM_DUBIOUS_DISC

	.2byte ITEM_DUSK_STONE

	.2byte ITEM_DYNITE_ORE

	.2byte ITEM_ELECTIRIZER

	.2byte ITEM_EVERSTONE

	.2byte ITEM_FIRE_STONE

	.2byte ITEM_FLOWER_SWEET

	.2byte ITEM_GALARICA_CUFF

	.2byte ITEM_GALARICA_TWIG

	.2byte ITEM_GALARICA_WREATH

	.2byte ITEM_GIMMIGHOUL_COIN

	.2byte ITEM_GRISEOUS_CORE

	.2byte ITEM_ICE_STONE

	.2byte ITEM_KINGS_ROCK

	.2byte ITEM_LEADERS_CREST

	.2byte ITEM_LEAF_STONE

	.2byte ITEM_LINKING_CORD

	.2byte ITEM_LOVE_SWEET

	.2byte ITEM_LUSTROUS_GLOBE

	.2byte ITEM_MAGMARIZER

	.2byte ITEM_MALICIOUS_ARMOR

	.2byte ITEM_MASTERPIECE_TEACUP

	.2byte ITEM_METAL_ALLOY

	.2byte ITEM_METAL_COAT

	.2byte ITEM_MOON_STONE

	.2byte ITEM_OVAL_STONE

	.2byte ITEM_PEAT_BLOCK

	.2byte ITEM_PRISM_SCALE

	.2byte ITEM_PROTECTOR

	.2byte ITEM_RAZOR_CLAW

	.2byte ITEM_RAZOR_FANG

	.2byte ITEM_REAPER_CLOTH

	.2byte ITEM_RIBBON_SWEET

	.2byte ITEM_SACHET

	.2byte ITEM_SHINY_STONE

	.2byte ITEM_STAR_SWEET

	.2byte ITEM_STRAWBERRY_SWEET

	.2byte ITEM_SUN_STONE

	.2byte ITEM_SWEET_APPLE

	.2byte ITEM_SYRUPY_APPLE

	.2byte ITEM_TART_APPLE

	.2byte ITEM_THUNDER_STONE

	.2byte ITEM_UNREMARKABLE_TEACUP

	.2byte ITEM_UPGRADE

	.2byte ITEM_WATER_STONE

	.2byte ITEM_WHIPPED_DREAM

	.2byte ITEM_ALOLA_POSTCARD

	.2byte ITEM_GALAR_POSTCARD

	.2byte ITEM_HISUI_POSTCARD

	.2byte ITEM_ABOMASITE

	.2byte ITEM_ABSOLITE

	.2byte ITEM_ABSOLITE_Z

	.2byte ITEM_AERODACTYLITE

	.2byte ITEM_AGGRONITE

	.2byte ITEM_NONE
LilycoveCity_DepartmentStore_2F_EventScript_ClerkRight::
	lock
	faceplayer
	message gText_HowMayIServeYou
	waitmessage
	pokemart LilycoveCity_DepartmentStore_2F_Pokemart2
	msgbox gText_PleaseComeAgain, MSGBOX_DEFAULT
	release
	end

	.align 2
LilycoveCity_DepartmentStore_2F_Pokemart2:







































	.2byte ITEM_ALAKAZITE

	.2byte ITEM_ALTARIANITE

	.2byte ITEM_AMPHAROSITE

	.2byte ITEM_AUDINITE

	.2byte ITEM_BANETTITE

	.2byte ITEM_BARBARACITE

	.2byte ITEM_BAXCALIBRITE

	.2byte ITEM_BEEDRILLITE

	.2byte ITEM_BLASTOISINITE

	.2byte ITEM_BLAZIKENITE

	.2byte ITEM_CAMERUPTITE

	.2byte ITEM_CHANDELURITE

	.2byte ITEM_CHARIZARDITE_X

	.2byte ITEM_CHARIZARDITE_Y

	.2byte ITEM_CHESNAUGHTITE

	.2byte ITEM_CHIMECHITE

	.2byte ITEM_CLEFABLITE

	.2byte ITEM_CRABOMINITE

	.2byte ITEM_DARKRANITE

	.2byte ITEM_DELPHOXITE

	.2byte ITEM_DIANCITE

	.2byte ITEM_DRAGALGITE

	.2byte ITEM_DRAGONINITE

	.2byte ITEM_DRAMPANITE

	.2byte ITEM_EELEKTROSSITE

	.2byte ITEM_EMBOARITE

	.2byte ITEM_EXCADRITE

	.2byte ITEM_FALINKSITE

	.2byte ITEM_FERALIGITE

	.2byte ITEM_FLOETTITE

	.2byte ITEM_FROSLASSITE

	.2byte ITEM_GALLADITE

	.2byte ITEM_GARCHOMPITE

	.2byte ITEM_GARCHOMPITE_Z

	.2byte ITEM_GARDEVOIRITE

	.2byte ITEM_GENGARITE

	.2byte ITEM_GLALITITE

	.2byte ITEM_GLIMMORANITE

	.2byte ITEM_GOLISOPITE

	.2byte ITEM_GOLURKITE

	.2byte ITEM_GRENINJITE

	.2byte ITEM_GYARADOSITE

	.2byte ITEM_HAWLUCHANITE

	.2byte ITEM_HEATRANITE

	.2byte ITEM_HERACRONITE

	.2byte ITEM_HOUNDOOMINITE

	.2byte ITEM_KANGASKHANITE

	.2byte ITEM_LATIASITE

	.2byte ITEM_LATIOSITE

	.2byte ITEM_LOPUNNITE

	.2byte ITEM_LUCARIONITE

	.2byte ITEM_LUCARIONITE_Z

	.2byte ITEM_MAGEARNITE

	.2byte ITEM_MALAMARITE

	.2byte ITEM_MANECTITE

	.2byte ITEM_MAWILITE

	.2byte ITEM_MEDICHAMITE

	.2byte ITEM_MEGANIUMITE

	.2byte ITEM_MEOWSTICITE

	.2byte ITEM_METAGROSSITE

	.2byte ITEM_MEWTWONITE_X

	.2byte ITEM_MEWTWONITE_Y

	.2byte ITEM_PIDGEOTITE

	.2byte ITEM_PINSIRITE

	.2byte ITEM_PYROARITE

	.2byte ITEM_RAICHUNITE_X

	.2byte ITEM_RAICHUNITE_Y

	.2byte ITEM_SABLENITE

	.2byte ITEM_SALAMENCITE

	.2byte ITEM_SCEPTILITE

	.2byte ITEM_SCIZORITE

	.2byte ITEM_SCOLIPITE

	.2byte ITEM_SCOVILLAINITE

	.2byte ITEM_SCRAFTINITE

	.2byte ITEM_SHARPEDONITE

	.2byte ITEM_SKARMORITE

	.2byte ITEM_SLOWBRONITE

	.2byte ITEM_STARAPTITE

	.2byte ITEM_STARMINITE

	.2byte ITEM_STEELIXITE

	.2byte ITEM_SWAMPERTITE

	.2byte ITEM_TATSUGIRINITE

	.2byte ITEM_TYRANITARITE

	.2byte ITEM_VENUSAURITE

	.2byte ITEM_VICTREEBELITE

	.2byte ITEM_ZERAORITE

	.2byte ITEM_ZYGARDITE

	.2byte ITEM_NONE
LilycoveCity_DepartmentStore_2F_Text_LearnToUseItemsProperly:
	.string "Learn to use items properly.\n"
	.string "That's basic, really.$"

LilycoveCity_DepartmentStore_2F_Text_GoodGiftForHusband:
	.string "My husband is waiting at home.\n"
	.string "What would make a good gift for him?$"

LilycoveCity_DepartmentStore_2F_Text_StockUpOnItems:
	.string "I'm leaving on a long journey soon.\n"
	.string "I need to stock up on items.$"

