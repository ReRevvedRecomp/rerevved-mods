#include <rex/system/mod_plugin.h>

#include <unique_unit_rules.h>

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

constexpr char kProviderId[] = "aeshur.cataphracts-defense";
constexpr char kRuleId[]     = "cataphract-defense";

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

class RomanCataphractsDefensePlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            resolveHostFunction<UniqueUnitRulesAbiVersionFn>(
                "UniqueUnitRulesAbiVersion");
        const auto registerRule =
            resolveHostFunction<RegisterUniqueUnitScalarRuleFn>(
                "RegisterUniqueUnitScalarRule");
        if (!version || !registerRule ||
            version() != UNIQUE_UNIT_RULES_ABI_VERSION)
        {
            return;
        }

        UniqueUnitScalarRule rule{};
        rule.structSize   = sizeof(rule);
        rule.civilization = CIVILIZATION_ROMAN;
        rule.baseUnitType = UNIT_TYPE_KNIGHTS;
        rule.identity     = UNIT_IDENTITY_CATAPHRACT;
        rule.property     = UNIQUE_UNIT_SCALAR_BASE_DEFENSE;
        rule.operation    = UNIQUE_UNIT_SCALAR_ADD;
        rule.value        = 1;
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
    return new RomanCataphractsDefensePlugin();
}
