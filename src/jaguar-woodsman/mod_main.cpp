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
Function ResolveHostFunction(const char* name)
{
#if defined(_WIN32)
    return reinterpret_cast<Function>(
        GetProcAddress(GetModuleHandleW(nullptr), name));
#else
    return reinterpret_cast<Function>(dlsym(RTLD_DEFAULT, name));
#endif
}

void RegisterRule(ReRevvedRegisterUnitCombatRuleFn register_rule,
                  const char*                      rule_id,
                  ReRevvedUnitCombatProperty       property)
{
    ReRevvedUnitCombatRule rule{};
    rule.struct_size      = sizeof(rule);
    rule.civilization     = REREVVED_CIVILIZATION_AZTEC;
    rule.base_unit_type   = REREVVED_UNIT_TYPE_WARRIOR;
    rule.identity         = REREVVED_UNIT_IDENTITY_JAGUAR_WARRIOR;
    rule.terrain          = REREVVED_TERRAIN_FOREST;
    rule.property         = property;
    rule.percentage_delta = 50;
    std::memcpy(rule.provider_id, kProviderId, sizeof(kProviderId));
    std::memcpy(rule.rule_id, rule_id, std::strlen(rule_id) + 1);
    register_rule(&rule);
}

class AztecJaguarForestCombatPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            ResolveHostFunction<ReRevvedUnitCombatRulesAbiVersionFn>(
                "ReRevvedUnitCombatRulesAbiVersion");
        const auto register_rule =
            ResolveHostFunction<ReRevvedRegisterUnitCombatRuleFn>(
                "ReRevvedRegisterUnitCombatRule");
        if (!version || !register_rule ||
            version() != REREVVED_UNIT_COMBAT_RULES_ABI_VERSION)
        {
            return;
        }

        RegisterRule(register_rule, "jaguar-warrior-forest-attack", REREVVED_UNIT_COMBAT_ATTACK);
        RegisterRule(register_rule, "jaguar-warrior-forest-defense", REREVVED_UNIT_COMBAT_DEFENSE);
    }
};

} // namespace

extern "C" REX_MOD_PLUGIN_EXPORT uint32_t rex_mod_abi_version()
{
    return rex::system::kModPluginAbiVersion;
}

extern "C" REX_MOD_PLUGIN_EXPORT rex::system::IModPlugin* rex_mod_create(
    uint32_t                           abi_version,
    const rex::system::ModHostContext* context)
{
    if (abi_version != rex::system::kModPluginAbiVersion || !context ||
        context->struct_size < sizeof(rex::system::ModHostContext))
    {
        return nullptr;
    }
    return new AztecJaguarForestCombatPlugin();
}
