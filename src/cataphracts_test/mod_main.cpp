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

constexpr char kProviderId[] = "aeshur.cataphracts-test";
constexpr char kRuleId[]     = "cataphract-attack";

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

class CataphractsTestPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            ResolveHostFunction<ReRevvedUniqueUnitRulesAbiVersionFn>(
                "ReRevvedUniqueUnitRulesAbiVersion");
        const auto register_rule =
            ResolveHostFunction<ReRevvedRegisterUniqueUnitScalarRuleFn>(
                "ReRevvedRegisterUniqueUnitScalarRule");
        if (!version || !register_rule ||
            version() != REREVVED_UNIQUE_UNIT_RULES_ABI_VERSION)
        {
            return;
        }

        ReRevvedUniqueUnitScalarRule rule{};
        rule.struct_size    = sizeof(rule);
        rule.civilization   = REREVVED_CIVILIZATION_ROMAN;
        rule.base_unit_type = REREVVED_UNIT_TYPE_KNIGHTS;
        rule.identity       = REREVVED_UNIT_IDENTITY_CATAPHRACT;
        rule.property       = REREVVED_UNIQUE_UNIT_SCALAR_EFFECTIVE_ATTACK;
        rule.operation      = REREVVED_UNIQUE_UNIT_SCALAR_REPLACE;
        rule.value          = 50;
        std::memcpy(rule.provider_id, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.rule_id, kRuleId, sizeof(kRuleId));
        register_rule(&rule);
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
    return new CataphractsTestPlugin();
}
