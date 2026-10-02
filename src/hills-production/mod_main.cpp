#include <rex/system/mod_plugin.h>

#include <terrain_yield_rules.h>

#include <cinttypes>
#include <cstdio>
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
            TerrainYieldRulesAbiVersionFn>(
            "TerrainYieldRulesAbiVersion");
        const auto registerRule = resolveHostFunction<
            RegisterTerrainYieldRuleFn>(
            "RegisterTerrainYieldRule");
        if (!version || !registerRule ||
            version() != TERRAIN_YIELD_RULES_ABI_VERSION)
        {
            return;
        }

        TerrainYieldRule rule{};
        rule.structSize = sizeof(rule);
        rule.terrain    = TERRAIN_HILL;
        rule.component  = TERRAIN_YIELD_PRODUCTION;
        rule.operation  = TERRAIN_YIELD_ADD;
        rule.value      = 1;
        std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.ruleId, kRuleId, sizeof(kRuleId));
        const int32_t result = registerRule(&rule);
        if (result != TERRAIN_YIELD_RULES_OK)
        {
            std::fprintf(stderr, "Hills Production: terrain yield registration rejected (%" PRId32 ").\n", result);
            return;
        }
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
