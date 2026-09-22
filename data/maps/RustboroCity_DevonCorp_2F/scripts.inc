RustboroCity_DevonCorp_2F_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, RustboroCity_DevonCorp_2F_OnTransition
	.byte 0

RustboroCity_DevonCorp_2F_OnTransition:
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	end

RustboroCity_DevonCorp_2F_EventScript_SetFossilReady::
	setvar VAR_FOSSIL_RESURRECTION_STATE, 2
	return

RustboroCity_DevonCorp_2F_EventScript_TalkToPokemonScientist::
	lock
	faceplayer
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	msgbox RustboroCity_DevonCorp_2F_Text_DeviceForTalkingToPokemon, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_BallScientist::
	lock
	faceplayer
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	goto_if_set FLAG_MET_DEVON_EMPLOYEE, RustboroCity_DevonCorp_2F_EventScript_DevelopedBalls
	msgbox RustboroCity_DevonCorp_2F_Text_DevelopingNewBalls, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_DevelopedBalls::
	msgbox RustboroCity_DevonCorp_2F_Text_WeFinallyMadeNewBalls, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_PokenavScientist::
	lock
	faceplayer
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	goto_if_set FLAG_RECEIVED_POKENAV, RustboroCity_DevonCorp_2F_EventScript_HasPokenav
	msgbox RustboroCity_DevonCorp_2F_Text_IMadePokenav, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_HasPokenav::
	msgbox RustboroCity_DevonCorp_2F_Text_WowThatsAPokenav, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_PokemonDreamsScientist::
	lock
	faceplayer
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	msgbox RustboroCity_DevonCorp_2F_Text_DeviceToVisualizePokemonDreams, MSGBOX_DEFAULT
	release
	end

@ RANDOMIZER_ALL_FOSSILS_BEGIN
RustboroCity_DevonCorp_2F_EventScript_FossilScientist::
	lock
	faceplayer
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 2, Randomizer_Fossil_EventScript_MonReady
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_StillRegenerating
	msgbox RustboroCity_DevonCorp_2F_Text_DevelopDeviceToResurrectFossils, MSGBOX_DEFAULT
	checkitem ITEM_HELIX_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferHelix
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_DOME_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferDome
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_OLD_AMBER
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferOldAmber
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_ROOT_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferRoot
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_CLAW_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferClaw
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_ARMOR_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferArmor
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_SKULL_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferSkull
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_COVER_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferCover
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_PLUME_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferPlume
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_JAW_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferJaw
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_SAIL_FOSSIL
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferSail
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_FOSSILIZED_BIRD
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferBird
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_FOSSILIZED_DINO
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferDino
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_FOSSILIZED_DRAKE
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferDrake
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	checkitem ITEM_FOSSILIZED_FISH
	call_if_eq VAR_RESULT, TRUE, Randomizer_Fossil_EventScript_OfferFish
	goto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, Randomizer_Fossil_EventScript_Submitted
	release
	end

Randomizer_Fossil_EventScript_Submitted::
	release
	end

RustboroCity_DevonCorp_2F_EventScript_StillRegenerating::
	msgbox RustboroCity_DevonCorp_2F_Text_FossilRegeneratorTakesTime, MSGBOX_DEFAULT
	release
	end

Randomizer_Fossil_EventScript_OfferHelix::
	bufferitemname STR_VAR_1, ITEM_HELIX_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_HELIX_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 1
	return

Randomizer_Fossil_EventScript_OfferDome::
	bufferitemname STR_VAR_1, ITEM_DOME_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_DOME_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 2
	return

Randomizer_Fossil_EventScript_OfferOldAmber::
	bufferitemname STR_VAR_1, ITEM_OLD_AMBER
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_OLD_AMBER
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 3
	return

Randomizer_Fossil_EventScript_OfferRoot::
	bufferitemname STR_VAR_1, ITEM_ROOT_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_ROOT_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 4
	return

Randomizer_Fossil_EventScript_OfferClaw::
	bufferitemname STR_VAR_1, ITEM_CLAW_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_CLAW_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 5
	return

Randomizer_Fossil_EventScript_OfferArmor::
	bufferitemname STR_VAR_1, ITEM_ARMOR_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_ARMOR_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 6
	return

Randomizer_Fossil_EventScript_OfferSkull::
	bufferitemname STR_VAR_1, ITEM_SKULL_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_SKULL_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 7
	return

Randomizer_Fossil_EventScript_OfferCover::
	bufferitemname STR_VAR_1, ITEM_COVER_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_COVER_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 8
	return

Randomizer_Fossil_EventScript_OfferPlume::
	bufferitemname STR_VAR_1, ITEM_PLUME_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_PLUME_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 9
	return

Randomizer_Fossil_EventScript_OfferJaw::
	bufferitemname STR_VAR_1, ITEM_JAW_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_JAW_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 10
	return

Randomizer_Fossil_EventScript_OfferSail::
	bufferitemname STR_VAR_1, ITEM_SAIL_FOSSIL
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_SAIL_FOSSIL
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 11
	return

Randomizer_Fossil_EventScript_OfferBird::
	bufferitemname STR_VAR_1, ITEM_FOSSILIZED_BIRD
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_FOSSILIZED_BIRD
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 12
	return

Randomizer_Fossil_EventScript_OfferDino::
	bufferitemname STR_VAR_1, ITEM_FOSSILIZED_DINO
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_FOSSILIZED_DINO
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 13
	return

Randomizer_Fossil_EventScript_OfferDrake::
	bufferitemname STR_VAR_1, ITEM_FOSSILIZED_DRAKE
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_FOSSILIZED_DRAKE
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 14
	return

Randomizer_Fossil_EventScript_OfferFish::
	bufferitemname STR_VAR_1, ITEM_FOSSILIZED_FISH
	msgbox Randomizer_Fossil_Text_OfferFossil, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn
	msgbox RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, MSGBOX_DEFAULT
	removeitem ITEM_FOSSILIZED_FISH
	setvar VAR_FOSSIL_RESURRECTION_STATE, 1
	setvar VAR_WHICH_FOSSIL_REVIVED, 15
	return

Randomizer_Fossil_EventScript_MonReady::
	call Randomizer_Fossil_EventScript_SetRevivedSpecies
	bufferspeciesname STR_VAR_2, VAR_TEMP_1
	msgbox RustboroCity_DevonCorp_2F_Text_FossilizedMonBroughtBackToLife, MSGBOX_DEFAULT
	copyvar VAR_TEMP_TRANSFERRED_SPECIES, VAR_TEMP_1
	givemon VAR_TEMP_1, 20
	goto_if_eq VAR_RESULT, MON_GIVEN_TO_PARTY, Randomizer_Fossil_EventScript_ReceiveParty
	goto_if_eq VAR_RESULT, MON_GIVEN_TO_PC, Randomizer_Fossil_EventScript_ReceivePC
	goto Common_EventScript_NoMoreRoomForPokemon
	end

Randomizer_Fossil_EventScript_ReceiveParty::
	call Randomizer_Fossil_EventScript_ReceivedFanfare
	msgbox gText_NicknameThisPokemon, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Randomizer_Fossil_EventScript_FinishReceiving
	call Common_EventScript_GetGiftMonPartySlot
	call Common_EventScript_NameReceivedPartyMon
	goto Randomizer_Fossil_EventScript_FinishReceiving
	end

Randomizer_Fossil_EventScript_ReceivePC::
	call Randomizer_Fossil_EventScript_ReceivedFanfare
	msgbox gText_NicknameThisPokemon, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, Randomizer_Fossil_EventScript_TransferToPC
	call Common_EventScript_NameReceivedBoxMon

Randomizer_Fossil_EventScript_TransferToPC::
	call Common_EventScript_TransferredToPC

Randomizer_Fossil_EventScript_FinishReceiving::
	setvar VAR_FOSSIL_RESURRECTION_STATE, 0
	setflag FLAG_RECEIVED_REVIVED_FOSSIL_MON
	release
	end

Randomizer_Fossil_EventScript_ReceivedFanfare::
	bufferspeciesname STR_VAR_2, VAR_TEMP_1
	playfanfare MUS_OBTAIN_ITEM
	message RustboroCity_DevonCorp_2F_Text_ReceivedMonFromResearcher
	waitmessage
	waitfanfare
	bufferspeciesname STR_VAR_1, VAR_TEMP_1
	return

Randomizer_Fossil_EventScript_SetRevivedSpecies::
	switch VAR_WHICH_FOSSIL_REVIVED
	case 1, Randomizer_Fossil_EventScript_SetSpeciesHelix
	case 2, Randomizer_Fossil_EventScript_SetSpeciesDome
	case 3, Randomizer_Fossil_EventScript_SetSpeciesOldAmber
	case 4, Randomizer_Fossil_EventScript_SetSpeciesRoot
	case 5, Randomizer_Fossil_EventScript_SetSpeciesClaw
	case 6, Randomizer_Fossil_EventScript_SetSpeciesArmor
	case 7, Randomizer_Fossil_EventScript_SetSpeciesSkull
	case 8, Randomizer_Fossil_EventScript_SetSpeciesCover
	case 9, Randomizer_Fossil_EventScript_SetSpeciesPlume
	case 10, Randomizer_Fossil_EventScript_SetSpeciesJaw
	case 11, Randomizer_Fossil_EventScript_SetSpeciesSail
	case 12, Randomizer_Fossil_EventScript_SetSpeciesBird
	case 13, Randomizer_Fossil_EventScript_SetSpeciesDino
	case 14, Randomizer_Fossil_EventScript_SetSpeciesDrake
	case 15, Randomizer_Fossil_EventScript_SetSpeciesFish
	return

Randomizer_Fossil_EventScript_SetSpeciesHelix::
	setvar VAR_TEMP_1, SPECIES_PORYGON_Z
	return

Randomizer_Fossil_EventScript_SetSpeciesDome::
	setvar VAR_TEMP_1, SPECIES_DRAGONAIR
	return

Randomizer_Fossil_EventScript_SetSpeciesOldAmber::
	setvar VAR_TEMP_1, SPECIES_TOGEKISS
	return

Randomizer_Fossil_EventScript_SetSpeciesRoot::
	setvar VAR_TEMP_1, SPECIES_PIKACHU_HOENN
	return

Randomizer_Fossil_EventScript_SetSpeciesClaw::
	setvar VAR_TEMP_1, SPECIES_PHANPY
	return

Randomizer_Fossil_EventScript_SetSpeciesArmor::
	setvar VAR_TEMP_1, SPECIES_MAGBY
	return

Randomizer_Fossil_EventScript_SetSpeciesSkull::
	setvar VAR_TEMP_1, SPECIES_BELLSPROUT
	return

Randomizer_Fossil_EventScript_SetSpeciesCover::
	setvar VAR_TEMP_1, SPECIES_ROSELIA
	return

Randomizer_Fossil_EventScript_SetSpeciesPlume::
	setvar VAR_TEMP_1, SPECIES_SUNKERN
	return

Randomizer_Fossil_EventScript_SetSpeciesJaw::
	setvar VAR_TEMP_1, SPECIES_ELEKID
	return

Randomizer_Fossil_EventScript_SetSpeciesSail::
	setvar VAR_TEMP_1, SPECIES_GULPIN
	return

Randomizer_Fossil_EventScript_SetSpeciesBird::
	setvar VAR_TEMP_1, SPECIES_PIDGEY
	return

Randomizer_Fossil_EventScript_SetSpeciesDino::
	setvar VAR_TEMP_1, SPECIES_QUAGSIRE
	return

Randomizer_Fossil_EventScript_SetSpeciesDrake::
	setvar VAR_TEMP_1, SPECIES_WIGLETT
	return

Randomizer_Fossil_EventScript_SetSpeciesFish::
	setvar VAR_TEMP_1, SPECIES_SLOWBRO
	return

Randomizer_Fossil_Text_OfferFossil:
	.string "I found your {STR_VAR_1}!\p"
	.string "Would you like me to bring its\n"
	.string "ancient POKéMON back to life?$"
@ RANDOMIZER_ALL_FOSSILS_END

RustboroCity_DevonCorp_2F_EventScript_MatchCallScientist::
	lock
	faceplayer
	call_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, RustboroCity_DevonCorp_2F_EventScript_SetFossilReady
	goto_if_ge VAR_RUSTBORO_CITY_STATE, 6, RustboroCity_DevonCorp_2F_EventScript_WorkOnNext
	msgbox RustboroCity_DevonCorp_2F_Text_DevelopNewPokenavFeature, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_EventScript_WorkOnNext::
	msgbox RustboroCity_DevonCorp_2F_Text_WhatToWorkOnNext, MSGBOX_DEFAULT
	release
	end

RustboroCity_DevonCorp_2F_Text_DeviceForTalkingToPokemon:
	.string "We're developing a device for talking\n"
	.string "with POKéMON.\p"
	.string "But we haven't had much success…$"

RustboroCity_DevonCorp_2F_Text_DevelopingNewBalls:
	.string "I'm developing new kinds of\n"
	.string "POKé BALLS…\p"
	.string "But I haven't made much headway…$"

RustboroCity_DevonCorp_2F_Text_WeFinallyMadeNewBalls:
	.string "We finally made new kinds of\n"
	.string "POKé BALLS!\p"
	.string "The REPEAT BALL makes it easier to\n"
	.string "catch POKéMON you've caught before.\p"
	.string "The TIMER BALL gets better at catching\n"
	.string "POKéMON the longer a battle runs.\p"
	.string "Both are proudly developed by\n"
	.string "the DEVON CORPORATION.\p"
	.string "Please give them a try!$"

RustboroCity_DevonCorp_2F_Text_IMadePokenav:
	.string "I made the POKéNAV!\p"
	.string "As an engineer, I feel blessed to have\n"
	.string "made something so great!$"

RustboroCity_DevonCorp_2F_Text_WowThatsAPokenav:
	.string "Oh, wow!\n"
	.string "That's a POKéNAV!\p"
	.string "It came about as a result of our\n"
	.string "PRESIDENT's desire to learn about\l"
	.string "the feelings of POKéMON.\p"
	.string "Would you like me to describe its\n"
	.string "features in detail?\p"
	.string "No, no. I think you'll find out just by\n"
	.string "trying the POKéNAV out.$"

RustboroCity_DevonCorp_2F_Text_DeviceToVisualizePokemonDreams:
	.string "I'm trying to develop a device that\n"
	.string "visually reproduces the dreams of\l"
	.string "POKéMON…\p"
	.string "But it's not going well.$"

RustboroCity_DevonCorp_2F_Text_DevelopDeviceToResurrectFossils:
	.string "I've been trying to develop a device\n"
	.string "that resurrects POKéMON from fossils…\p"
	.string "And, it's working!$"

RustboroCity_DevonCorp_2F_Text_WantToBringFossilBackToLife:
	.string "Wait! That thing you have there…\n"
	.string "Is that a POKéMON fossil?\p"
	.string "Would you like to bring that POKéMON\n"
	.string "back to life?\p"
	.string "I can with my newly developed\n"
	.string "FOSSIL REGENERATOR.$"

RustboroCity_DevonCorp_2F_Text_OhIsThatSo:
	.string "Oh, is that so?\p"
	.string "DEVON's technological expertise\n"
	.string "is outstanding, I tell you.$"

RustboroCity_DevonCorp_2F_Text_TwoFossilsPickOne:
	.string "Oh, now that's a surprise!\n"
	.string "You have not one, but two, fossils?\p"
	.string "Unfortunately, my machine can only\n"
	.string "regenerate one POKéMON at a time.\p"
	.string "Would you like to pick one of your\n"
	.string "fossils for regeneration?$"

RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher:
	.string "Excellent!\n"
	.string "Let's do this right away.\p"
	.string "{PLAYER} handed the {STR_VAR_1} to\n"
	.string "the DEVON RESEARCHER.$"

RustboroCity_DevonCorp_2F_Text_FossilRegeneratorTakesTime:
	.string "The FOSSIL REGENERATOR, which I made,\n"
	.string "is incredible.\p"
	.string "But it has one drawback--it takes\n"
	.string "a long time to work.\p"
	.string "So, uh… How about you go for a stroll\n"
	.string "and look around for a while?$"

RustboroCity_DevonCorp_2F_Text_FossilizedMonBroughtBackToLife:
	.string "Thanks for waiting!\p"
	.string "Your fossilized POKéMON has been\n"
	.string "brought back to life!\p"
	.string "The fossil was an ancient POKéMON.\n"
	.string "{STR_VAR_2}, it was!$"

RustboroCity_DevonCorp_2F_Text_ReceivedMonFromResearcher:
	.string "{PLAYER} received {STR_VAR_2} from\n"
	.string "the DEVON RESEARCHER.$"

@ Unused
RustboroCity_DevonCorp_2F_Text_TooManyPokemon:
	.string "Uh-oh, you've got too many POKéMON.\n"
	.string "You have no room for this one.$"

RustboroCity_DevonCorp_2F_Text_DevelopNewPokenavFeature:
	.string "I'm trying to develop a new feature\n"
	.string "for the POKéNAV…\p"
	.string "But it's not going well.$"

RustboroCity_DevonCorp_2F_Text_WhatToWorkOnNext:
	.string "Well, now what shall I work on\n"
	.string "developing next?\p"
	.string "Our company allows us to make our\n"
	.string "inspirations into reality.\p"
	.string "One couldn't ask for a better\n"
	.string "environment as an engineer.$"

