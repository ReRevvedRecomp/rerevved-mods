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

void registerWoodsmanRule(RegisterUnitCombatRuleFn registerRule,
                          const char*              ruleId,
                          UnitCombatProperty       property)
{
    UnitCombatRule rule{};
    rule.structSize      = sizeof(rule);
    rule.civilization    = CIVILIZATION_AZTEC;
    rule.baseUnitType    = UNIT_TYPE_WARRIOR;
    rule.identity        = UNIT_IDENTITY_JAGUAR_WARRIOR;
    rule.terrain         = TERRAIN_FOREST;
    rule.property        = property;
    rule.percentageDelta = 50;
    std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
    std::memcpy(rule.ruleId, ruleId, std::strlen(ruleId) + 1);
    registerRule(&rule);
}

class JaguarWoodsmanPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            resolveHostFunction<UnitCombatRulesAbiVersionFn>(
                "UnitCombatRulesAbiVersion");
        const auto registerRule =
            resolveHostFunction<RegisterUnitCombatRuleFn>(
                "RegisterUnitCombatRule");
        if (!version || !registerRule ||
            version() != UNIT_COMBAT_RULES_ABI_VERSION)
        {
            return;
        }

        registerWoodsmanRule(registerRule, "jaguar-warrior-forest-attack", UNIT_COMBAT_ATTACK);
        registerWoodsmanRule(registerRule, "jaguar-warrior-forest-defense", UNIT_COMBAT_DEFENSE);
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
    return new JaguarWoodsmanPlugin();
}
