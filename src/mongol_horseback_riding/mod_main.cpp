#include <rex/system/mod_plugin.h>

#include <unique_era_abilities.h>

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

constexpr char kProviderId[] = "aeshur.mongol-horseback-riding";
constexpr char kRuleId[]     = "mongol-ancient-horseback-riding";

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

class MongolHorsebackRidingPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            ResolveHostFunction<ReRevvedUniqueEraAbilitiesAbiVersionFn>(
                "ReRevvedUniqueEraAbilitiesAbiVersion");
        const auto register_rule = ResolveHostFunction<
            ReRevvedRegisterUniqueEraAbilityReplacementFn>(
            "ReRevvedRegisterUniqueEraAbilityReplacement");
        if (!version || !register_rule ||
            version() != REREVVED_UNIQUE_ERA_ABILITIES_ABI_VERSION)
        {
            return;
        }

        ReRevvedUniqueEraAbilityReplacement rule{};
        rule.struct_size  = sizeof(rule);
        rule.civilization = REREVVED_CIVILIZATION_MONGOLIAN;
        rule.unlock_era   = REREVVED_UNIQUE_ERA_ANCIENT;
        rule.replacement_ability =
            REREVVED_UNIQUE_ERA_ABILITY_KNOWLEDGE_OF_HORSEBACK_RIDING;
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
    return new MongolHorsebackRidingPlugin();
}
