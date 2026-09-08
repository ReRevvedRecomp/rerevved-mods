#include <rex/system/mod_plugin.h>

#include <terrain_yield_rules.h>

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

constexpr char kProviderId[] = "aeshur.hills-production";
constexpr char kRuleId[]     = "hills-production";

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

class HillsProductionPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version = resolveHostFunction<
            ReRevvedTerrainYieldRulesAbiVersionFn>(
            "ReRevvedTerrainYieldRulesAbiVersion");
        const auto registerRule = resolveHostFunction<
            ReRevvedRegisterTerrainYieldRuleFn>(
            "ReRevvedRegisterTerrainYieldRule");
        if (!version || !registerRule ||
            version() != REREVVED_TERRAIN_YIELD_RULES_ABI_VERSION)
        {
            return;
        }

        ReRevvedTerrainYieldRule rule{};
        rule.structSize = sizeof(rule);
        rule.terrain    = REREVVED_TERRAIN_HILL;
        rule.component  = REREVVED_TERRAIN_YIELD_PRODUCTION;
        rule.operation  = REREVVED_TERRAIN_YIELD_ADD;
        rule.value      = 1;
        std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.ruleId, kRuleId, sizeof(kRuleId));
        registerRule(&rule);
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
    return new HillsProductionPlugin();
}
