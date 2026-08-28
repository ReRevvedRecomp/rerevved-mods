#include <rex/system/mod_plugin.h>

#include <rex/logging.h>

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

constexpr char kProviderId[] = "aeshur.roman-rush-test";
constexpr char kRuleId[]     = "roman-medieval-rush";

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

class RomanRushTestPlugin final : public rex::system::IModPlugin
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
        const auto get_rule_count = ResolveHostFunction<
            ReRevvedGetUniqueEraAbilityRuleCountFn>(
            "ReRevvedGetUniqueEraAbilityRuleCount");
        const auto get_rule =
            ResolveHostFunction<ReRevvedGetUniqueEraAbilityRuleFn>(
                "ReRevvedGetUniqueEraAbilityRule");
        const auto evaluate = ResolveHostFunction<
            ReRevvedEvaluateUniqueEraAbilityCellFn>(
            "ReRevvedEvaluateUniqueEraAbilityCell");
        if (!version || !register_rule || !get_rule_count || !get_rule ||
            !evaluate ||
            version() != REREVVED_UNIQUE_ERA_ABILITIES_ABI_VERSION)
        {
            return;
        }

        ReRevvedUniqueEraAbilityReplacement rule{};
        rule.struct_size  = sizeof(rule);
        rule.civilization = REREVVED_CIVILIZATION_ROMAN;
        rule.unlock_era   = REREVVED_UNIQUE_ERA_MEDIEVAL;
        rule.replacement_ability =
            REREVVED_UNIQUE_ERA_ABILITY_UNIT_RUSH_HALF_COST;
        std::memcpy(rule.provider_id, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.rule_id, kRuleId, sizeof(kRuleId));
        const int32_t registration_result = register_rule(&rule);
        if (registration_result != REREVVED_UNIQUE_ERA_ABILITIES_OK)
        {
            REXSYS_ERROR("Roman Rush Test registration failed: {}",
                         registration_result);
            return;
        }

        uint32_t                         rule_count = 0;
        ReRevvedUniqueEraAbilityRuleInfo rule_info{};
        rule_info.struct_size = sizeof(rule_info);
        ReRevvedUniqueEraAbilityCellQuery query{};
        query.struct_size  = sizeof(query);
        query.civilization = REREVVED_CIVILIZATION_ROMAN;
        query.unlock_era   = REREVVED_UNIQUE_ERA_MEDIEVAL;
        query.native_ability =
            REREVVED_UNIQUE_ERA_ABILITY_WONDERS_HALF_COST;
        ReRevvedUniqueEraAbilityCellEvaluation evaluation{};
        evaluation.struct_size = sizeof(evaluation);

        const int32_t count_result = get_rule_count(&rule_count);
        const int32_t rule_result =
            rule_count == 0
                ? REREVVED_UNIQUE_ERA_ABILITIES_ERR_INVALID_ARGUMENT
                : get_rule(0, &rule_info, sizeof(rule_info));
        const int32_t evaluation_result =
            evaluate(&query, &evaluation, sizeof(evaluation));
        if (count_result != REREVVED_UNIQUE_ERA_ABILITIES_OK ||
            rule_result != REREVVED_UNIQUE_ERA_ABILITIES_OK ||
            evaluation_result != REREVVED_UNIQUE_ERA_ABILITIES_OK)
        {
            REXSYS_ERROR(
                "Roman Rush Test readback failed: count={} rule={} evaluation={}",
                count_result,
                rule_result,
                evaluation_result);
            return;
        }

        REXSYS_INFO(
            "UEA_READBACK provider={} rule={} civilization={} era={} "
            "rule_count={} native={} effective={} replacements={} flags=0x{:08X}",
            rule_info.provider_id,
            rule_info.rule_id,
            rule_info.civilization,
            rule_info.unlock_era,
            rule_count,
            evaluation.native_ability,
            evaluation.effective_ability,
            evaluation.replacement_count,
            evaluation.status_flags);
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
    return new RomanRushTestPlugin();
}
