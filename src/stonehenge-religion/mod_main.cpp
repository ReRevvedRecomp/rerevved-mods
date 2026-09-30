#include <rex/system/mod_plugin.h>

#include <wonder_effect_rules.h>

#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <new>

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

constexpr char kProviderId[] = "aeshur.stonehenge-religion";
constexpr char kRuleId[]     = "stonehenge-religion-culture";

template <typename Function>
Function resolveHostFunction(const char* name)
{
#if defined(_WIN32)
    const HMODULE host = GetModuleHandleW(nullptr);
    return host ? reinterpret_cast<Function>(GetProcAddress(host, name)) : nullptr;
#else
    return reinterpret_cast<Function>(dlsym(RTLD_DEFAULT, name));
#endif
}

class StonehengeReligionPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version      = resolveHostFunction<WonderEffectRulesAbiVersionFn>("WonderEffectRulesAbiVersion");
        const auto getSupport   = resolveHostFunction<GetWonderEffectSupportFn>("GetWonderEffectSupport");
        const auto registerRule = resolveHostFunction<RegisterWonderEffectRuleFn>("RegisterWonderEffectRule");
        if (!version || !getSupport || !registerRule)
        {
            std::fprintf(stderr, "Stonehenge Religion: required title API exports are missing.\n");
            return;
        }
        if (version() != WONDER_EFFECT_RULES_ABI_VERSION)
        {
            std::fprintf(stderr, "Stonehenge Religion: incompatible title API.\n");
            return;
        }

        WonderEffectSupport support{};
        const int32_t       supportResult = getSupport(&support, sizeof(support));
        if (supportResult != WONDER_EFFECT_RULES_OK)
        {
            std::fprintf(stderr, "Stonehenge Religion: support query failed (%" PRId32 ").\n", supportResult);
            return;
        }
        if (support.structSize < sizeof(support) || support.runtimeAvailable > 1)
        {
            std::fprintf(stderr, "Stonehenge Religion: invalid runtime support response.\n");
            return;
        }
        if (!support.runtimeAvailable)
        {
            std::fprintf(stderr, "Stonehenge Religion: title runtime integration unavailable; no rule registered.\n");
            return;
        }

        WonderEffectRule rule{};
        rule.structSize = sizeof(rule);
        rule.effect     = WONDER_EFFECT_STONEHENGE_RELIGION_CULTURE;
        std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.ruleId, kRuleId, sizeof(kRuleId));
        const int32_t result = registerRule(&rule);
        if (result != WONDER_EFFECT_RULES_OK)
        {
            std::fprintf(stderr, "Stonehenge Religion: registration rejected (%" PRId32 ").\n", result);
            return;
        }
        std::fprintf(stderr, "Stonehenge Religion: rule registered.\n");
    }
};

} // namespace

extern "C" REX_MOD_PLUGIN_EXPORT uint32_t rex_mod_abi_version()
{
    return rex::system::kModPluginAbiVersion;
}

extern "C" REX_MOD_PLUGIN_EXPORT rex::system::IModPlugin* rex_mod_create(
    uint32_t abiVersion, const rex::system::ModHostContext* context)
{
    if (abiVersion != rex::system::kModPluginAbiVersion || !context ||
        context->struct_size < sizeof(rex::system::ModHostContext))
    {
        return nullptr;
    }
    return new (std::nothrow) StonehengeReligionPlugin();
}
