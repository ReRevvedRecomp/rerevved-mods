#include <rex/system/mod_plugin.h>

#include <unit_combat_rules.h>

#include <cstdint>
#include <cstring>

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

constexpr char kProviderId[] = "aeshur.jaguar-woodsman";

template <typename Function>
Function resolveHostFunction(const char* name)
{
#if defined(_WIN32)
    return reinterpret_cast<Function>(
        GetProcAddress(GetModuleHandleW(nullptr), name));
#else
    return reinterpret_cast<Function>(dlsym(RTLD_DEFAULT, name));
#endif
}

void registerForestRule(ReRevvedRegisterUnitCombatRuleFn registerRule,
                        const char*                      ruleId,
                        ReRevvedUnitCombatProperty       property)
{
    ReRevvedUnitCombatRule rule{};
    rule.structSize      = sizeof(rule);
    rule.civilization    = REREVVED_CIVILIZATION_AZTEC;
    rule.baseUnitType    = REREVVED_UNIT_TYPE_WARRIOR;
    rule.identity        = REREVVED_UNIT_IDENTITY_JAGUAR_WARRIOR;
    rule.terrain         = REREVVED_TERRAIN_FOREST;
    rule.property        = property;
    rule.percentageDelta = 50;
    std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
    std::memcpy(rule.ruleId, ruleId, std::strlen(ruleId) + 1);
    registerRule(&rule);
}

class AztecJaguarForestCombatPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            resolveHostFunction<ReRevvedUnitCombatRulesAbiVersionFn>(
                "ReRevvedUnitCombatRulesAbiVersion");
        const auto registerRule =
            resolveHostFunction<ReRevvedRegisterUnitCombatRuleFn>(
                "ReRevvedRegisterUnitCombatRule");
        if (!version || !registerRule ||
            version() != REREVVED_UNIT_COMBAT_RULES_ABI_VERSION)
        {
            return;
        }

        registerForestRule(registerRule, "jaguar-warrior-forest-attack", REREVVED_UNIT_COMBAT_ATTACK);
        registerForestRule(registerRule, "jaguar-warrior-forest-defense", REREVVED_UNIT_COMBAT_DEFENSE);
    }
};

} // namespace

extern "C" REX_MOD_PLUGIN_EXPORT uint32_t rex_mod_abi_version()
{
    return rex::system::kModPluginAbiVersion;
}

extern "C" REX_MOD_PLUGIN_EXPORT rex::system::IModPlugin* rex_mod_create(
    uint32_t                           abiVersion,
    const rex::system::ModHostContext* context)
{
    if (abiVersion != rex::system::kModPluginAbiVersion || !context ||
        context->struct_size < sizeof(rex::system::ModHostContext))
    {
        return nullptr;
    }
    return new AztecJaguarForestCombatPlugin();
}
