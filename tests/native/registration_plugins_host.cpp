#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <terrain_yield_rules.h>
#include <unique_unit_rules.h>
#include <unit_combat_rules.h>
#include <unit_effect_rules.h>
#include <unit_movement_rules.h>
#include <unit_production_cost_rules.h>

#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#else
#include <dlfcn.h>
#endif

namespace
{

std::string kind;
std::string mode;
unsigned    gameplayCalls    = 0;
unsigned    acceptedGameplay = 0;
unsigned    textCalls        = 0;
int32_t     rejectedResult   = 0;
bool        validRequests    = true;

bool check(bool condition, const char* message)
{
    if (!condition)
    {
        std::fprintf(stderr, "Host check failed: %s\n", message);
    }
    return condition;
}

template <typename Rule>
void identify(Rule& rule, const char* ruleId)
{
    rule.structSize            = sizeof(rule);
    const std::string provider = "aeshur." + kind;
    std::memcpy(rule.providerId, provider.c_str(), provider.size() + 1);
    std::memcpy(rule.ruleId, ruleId, std::strlen(ruleId) + 1);
}

template <typename Rule>
void checkRule(const Rule* actual, const Rule& expected, const char* expectedKind)
{
    validRequests = check(kind == expectedKind && actual && std::memcmp(actual, &expected, sizeof(expected)) == 0,
                          "exact rule declaration") &&
                    validRequests;
}

int32_t gameplayResult(int32_t ok, int32_t duplicate, int32_t internal, int32_t invalid)
{
    ++gameplayCalls;
    int32_t result = ok;
    if ((mode == "gameplay-first" && gameplayCalls == 1) ||
        (mode == "gameplay-second" && gameplayCalls == 2) ||
        (kind == "hills-production" && mode == "duplicate"))
    {
        result = duplicate;
    }
    else if (kind == "hills-production" && mode == "internal")
    {
        result = internal;
    }
    else if (kind == "hills-production" && mode == "invalid")
    {
        result = invalid;
    }
    if (result == ok)
    {
        ++acceptedGameplay;
    }
    else
    {
        rejectedResult = result;
    }
    return result;
}

unsigned gameplayRuleCount()
{
    return kind == "hoplite-loyalty" || kind == "jaguar-woodsman" ? 2u : 1u;
}

const char* displayName()
{
    if (kind == "hills-production")
    {
        return "Hills Production";
    }
    if (kind == "cataphracts-defense")
    {
        return "Cataphracts Defense";
    }
    if (kind == "hoplite-loyalty")
    {
        return "Hoplite Loyalty";
    }
    if (kind == "jaguar-woodsman")
    {
        return "Jaguar Woodsman";
    }
    if (kind == "keshik-movement")
    {
        return "Keshik Movement";
    }
    return "Mongol Horseback";
}

} // namespace

extern "C" uint32_t TerrainYieldRulesAbiVersion()
{
    return TERRAIN_YIELD_RULES_ABI_VERSION;
}

extern "C" uint32_t UniqueUnitRulesAbiVersion()
{
    return UNIQUE_UNIT_RULES_ABI_VERSION;
}

extern "C" uint32_t UnitEffectRulesAbiVersion()
{
    return UNIT_EFFECT_RULES_ABI_VERSION;
}

extern "C" uint32_t UnitProductionCostRulesAbiVersion()
{
    return UNIT_PRODUCTION_COST_RULES_ABI_VERSION;
}

extern "C" uint32_t UnitCombatRulesAbiVersion()
{
    return UNIT_COMBAT_RULES_ABI_VERSION;
}

extern "C" uint32_t UnitMovementRulesAbiVersion()
{
    return UNIT_MOVEMENT_RULES_ABI_VERSION;
}

extern "C" uint32_t EraAbilitiesAbiVersion()
{
    return ERA_ABILITIES_ABI_VERSION;
}

extern "C" uint32_t NationSelectTextAbiVersion()
{
    return NATION_SELECT_TEXT_ABI_VERSION;
}

extern "C" int32_t RegisterTerrainYieldRule(const TerrainYieldRule* rule)
{
    TerrainYieldRule expected{};
    identify(expected, "hills-production");
    expected.terrain   = TERRAIN_HILL;
    expected.component = TERRAIN_YIELD_PRODUCTION;
    expected.operation = TERRAIN_YIELD_ADD;
    expected.value     = 1;
    checkRule(rule, expected, "hills-production");
    return gameplayResult(TERRAIN_YIELD_RULES_OK, TERRAIN_YIELD_RULES_ERR_DUPLICATE_RULE_ID, TERRAIN_YIELD_RULES_ERR_INTERNAL, TERRAIN_YIELD_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterUniqueUnitScalarRule(const UniqueUnitScalarRule* rule)
{
    UniqueUnitScalarRule expected{};
    identify(expected, "cataphract-defense");
    expected.civilization = CIVILIZATION_ROMAN;
    expected.baseUnitType = UNIT_TYPE_KNIGHTS;
    expected.identity     = UNIT_IDENTITY_CATAPHRACT;
    expected.property     = UNIQUE_UNIT_SCALAR_BASE_DEFENSE;
    expected.operation    = UNIQUE_UNIT_SCALAR_ADD;
    expected.value        = 1;
    checkRule(rule, expected, "cataphracts-defense");
    return gameplayResult(UNIQUE_UNIT_RULES_OK, UNIQUE_UNIT_RULES_ERR_DUPLICATE_RULE_ID, UNIQUE_UNIT_RULES_ERR_INTERNAL, UNIQUE_UNIT_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterUnitEffectRule(const UnitEffectRule* rule)
{
    UnitEffectRule expected{};
    identify(expected, "hoplite-loyalty");
    expected.civilization = CIVILIZATION_GREEK;
    expected.baseUnitType = UNIT_TYPE_PHALANX;
    expected.identity     = UNIT_IDENTITY_HOPLITE;
    expected.effect       = UNIT_EFFECT_CREATION_LOYALTY;
    checkRule(rule, expected, "hoplite-loyalty");
    validRequests = check(gameplayCalls == 0, "Loyalty registers first") && validRequests;
    return gameplayResult(UNIT_EFFECT_RULES_OK, UNIT_EFFECT_RULES_ERR_DUPLICATE_RULE_ID, UNIT_EFFECT_RULES_ERR_INTERNAL, UNIT_EFFECT_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterUnitProductionCostRule(const UnitProductionCostRule* rule)
{
    UnitProductionCostRule expected{};
    identify(expected, "hoplite-production-cost");
    expected.civilization    = CIVILIZATION_GREEK;
    expected.baseUnitType    = UNIT_TYPE_PHALANX;
    expected.identity        = UNIT_IDENTITY_HOPLITE;
    expected.percentageDelta = -30;
    checkRule(rule, expected, "hoplite-loyalty");
    validRequests = check(gameplayCalls == 1 && acceptedGameplay == 1, "production cost follows accepted Loyalty") && validRequests;
    return gameplayResult(UNIT_PRODUCTION_COST_RULES_OK, UNIT_PRODUCTION_COST_RULES_ERR_DUPLICATE_RULE_ID, UNIT_PRODUCTION_COST_RULES_ERR_INTERNAL, UNIT_PRODUCTION_COST_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterUnitCombatRule(const UnitCombatRule* rule)
{
    UnitCombatRule expected{};
    identify(expected, gameplayCalls == 0 ? "jaguar-warrior-forest-attack" : "jaguar-warrior-forest-defense");
    expected.civilization    = CIVILIZATION_AZTEC;
    expected.baseUnitType    = UNIT_TYPE_WARRIOR;
    expected.identity        = UNIT_IDENTITY_JAGUAR_WARRIOR;
    expected.terrain         = TERRAIN_FOREST;
    expected.property        = gameplayCalls == 0 ? UNIT_COMBAT_ATTACK : UNIT_COMBAT_DEFENSE;
    expected.percentageDelta = 50;
    checkRule(rule, expected, "jaguar-woodsman");
    validRequests = check(gameplayCalls < 2 && acceptedGameplay == gameplayCalls, "attack registers before defense") && validRequests;
    return gameplayResult(UNIT_COMBAT_RULES_OK, UNIT_COMBAT_RULES_ERR_DUPLICATE_RULE_ID, UNIT_COMBAT_RULES_ERR_INTERNAL, UNIT_COMBAT_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterUnitMovementRule(const UnitMovementRule* rule)
{
    UnitMovementRule expected{};
    identify(expected, "keshik-movement");
    expected.civilization = CIVILIZATION_MONGOLIAN;
    expected.baseUnitType = UNIT_TYPE_HORSEMEN;
    expected.identity     = UNIT_IDENTITY_KESHIK;
    expected.value        = 1;
    checkRule(rule, expected, "keshik-movement");
    return gameplayResult(UNIT_MOVEMENT_RULES_OK, UNIT_MOVEMENT_RULES_ERR_DUPLICATE_RULE_ID, UNIT_MOVEMENT_RULES_ERR_INTERNAL, UNIT_MOVEMENT_RULES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterEraAbilityReplacement(const EraAbilityReplacement* rule)
{
    EraAbilityReplacement expected{};
    identify(expected, "mongol-ancient-horseback-riding");
    expected.civilization       = CIVILIZATION_MONGOLIAN;
    expected.unlockEra          = UNLOCK_ERA_ANCIENT;
    expected.replacementAbility = ERA_ABILITY_KNOWLEDGE_OF_HORSEBACK_RIDING;
    checkRule(rule, expected, "mongol-horseback");
    return gameplayResult(ERA_ABILITIES_OK, ERA_ABILITIES_ERR_DUPLICATE_RULE_ID, ERA_ABILITIES_ERR_INTERNAL, ERA_ABILITIES_ERR_INVALID_ARGUMENT);
}

extern "C" int32_t RegisterNationSelectTextRule(const NationSelectTextRule* rule)
{
    ++textCalls;
    NationSelectTextRule expected{};
    const char*          text = nullptr;
    expected.surface          = NATION_SELECT_TEXT_SURFACE_UNIQUE_UNIT;
    expected.unlockEra        = NATION_SELECT_TEXT_SELECTOR_UNUSED;
    expected.displayForm      = UNIT_DISPLAY_FORM_UNIT;
    if (kind == "cataphracts-defense")
    {
        identify(expected, "cataphract-defense-text");
        expected.civilization = CIVILIZATION_ROMAN;
        expected.baseUnitType = UNIT_TYPE_KNIGHTS;
        expected.identity     = UNIT_IDENTITY_CATAPHRACT;
        text                  = "Cataphract - Knight with +1 base Defense";
    }
    else if (kind == "hoplite-loyalty")
    {
        identify(expected, "hoplite-loyalty-text");
        expected.civilization = CIVILIZATION_GREEK;
        expected.baseUnitType = UNIT_TYPE_PHALANX;
        expected.identity     = UNIT_IDENTITY_HOPLITE;
        text                  = "Hoplite - Starts with Loyalty; costs 10 Production";
    }
    else if (kind == "jaguar-woodsman")
    {
        identify(expected, "jaguar-woodsman-text");
        expected.civilization = CIVILIZATION_AZTEC;
        expected.baseUnitType = UNIT_TYPE_WARRIOR;
        expected.identity     = UNIT_IDENTITY_JAGUAR_WARRIOR;
        text                  = "Jaguar Warrior - Warrior with +50% Attack and Defense in Forest";
    }
    else if (kind == "keshik-movement")
    {
        identify(expected, "keshik-movement-text");
        expected.civilization = CIVILIZATION_MONGOLIAN;
        expected.baseUnitType = UNIT_TYPE_HORSEMEN;
        expected.identity     = UNIT_IDENTITY_KESHIK;
        text                  = "Keshik - Horseman with +1 movement";
    }
    else if (kind == "mongol-horseback")
    {
        identify(expected, "mongol-ancient-horseback-riding-text");
        expected.surface      = NATION_SELECT_TEXT_SURFACE_ERA_ABILITY;
        expected.civilization = CIVILIZATION_MONGOLIAN;
        expected.unlockEra    = UNLOCK_ERA_ANCIENT;
        expected.ability      = ERA_ABILITY_KNOWLEDGE_OF_HORSEBACK_RIDING;
        expected.baseUnitType = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        expected.identity     = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        expected.displayForm  = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text                  = "Knowledge of Horseback Riding";
    }
    if (text)
    {
        std::memcpy(expected.text, text, std::strlen(text) + 1);
    }
    validRequests        = check(text && rule && std::memcmp(rule, &expected, sizeof(expected)) == 0,
                                 "exact text declaration") &&
                           validRequests;
    validRequests        = check(acceptedGameplay == gameplayRuleCount() && gameplayCalls == acceptedGameplay,
                                 "text follows accepted gameplay rules") &&
                           validRequests;
    const int32_t result = mode == "duplicate" ? NATION_SELECT_TEXT_ERR_DUPLICATE_RULE_ID : mode == "internal" ? NATION_SELECT_TEXT_ERR_INTERNAL
                                                                                        : mode == "invalid"    ? NATION_SELECT_TEXT_ERR_INVALID_ARGUMENT
                                                                                                               : NATION_SELECT_TEXT_OK;
    if (result != NATION_SELECT_TEXT_OK)
    {
        rejectedResult = result;
    }
    return result;
}

int main(int argc, char** argv)
{
    if (argc != 4)
    {
        std::fprintf(stderr, "Expected: package-id mode plugin-path\n");
        return 1;
    }
    kind = argv[1];
    mode = argv[2];
#if defined(_WIN32)
    const auto module  = LoadLibraryW(std::filesystem::path(argv[3]).c_str());
    const auto resolve = [module](const char* name)
    {
        return GetProcAddress(module, name);
    };
#else
    const auto module  = dlopen(argv[3], RTLD_NOW | RTLD_LOCAL);
    const auto resolve = [module](const char* name)
    {
        return dlsym(module, name);
    };
#endif
    if (!check(module != nullptr, "load compiled plugin"))
    {
        return 1;
    }
    const auto abi    = reinterpret_cast<rex::system::ModAbiVersionFn>(resolve("rex_mod_abi_version"));
    const auto create = reinterpret_cast<rex::system::ModCreateFn>(resolve("rex_mod_create"));
    if (!check(abi && create && abi() == rex::system::kModPluginAbiVersion, "plugin exports and ABI"))
    {
        return 1;
    }
    rex::system::ModHostContext context{};
    context.struct_size = sizeof(context);
    auto* plugin        = create(abi(), &context);
    if (!check(plugin != nullptr, "create plugin"))
    {
        return 1;
    }
    plugin->OnModuleLaunched();
    plugin->OnShutdown();
    delete plugin;
#if defined(_WIN32)
    FreeLibrary(module);
#else
    dlclose(module);
#endif
    const bool     gameplayRejected = mode == "gameplay-first" || mode == "gameplay-second";
    const unsigned expectedCalls    = mode == "gameplay-first" ? 1u : gameplayRuleCount();
    const bool     rejected         = mode != "success";
    const unsigned expectedAccepted = gameplayRejected || (kind == "hills-production" && rejected) ? expectedCalls - 1 : expectedCalls;
    const unsigned expectedText     = kind == "hills-production" || gameplayRejected ? 0u : 1u;
    bool           passed           = check(gameplayCalls == expectedCalls && acceptedGameplay == expectedAccepted && textCalls == expectedText,
                                            "registration counts and dependent text gate") &&
                                      validRequests;
    passed                          = check((rejectedResult != 0) == rejected, "controlled rejection reached") && passed;
    // The CTest driver compares this expected diagnostic with the plugin's stderr.
    if (rejected && !gameplayRejected)
    {
        if (kind == "hills-production")
        {
            std::printf("%s: terrain yield registration rejected (%" PRId32 ").\n", displayName(), rejectedResult);
        }
        else
        {
            std::printf("%s: nation select text registration rejected (%" PRId32 "); gameplay %s.\n",
                        displayName(),
                        rejectedResult,
                        gameplayRuleCount() == 2 ? "rules remain registered" : "rule remains registered");
        }
    }
    return passed ? 0 : 1;
}
