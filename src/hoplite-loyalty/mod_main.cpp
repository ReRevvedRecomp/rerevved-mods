#include <rex/system/mod_plugin.h>

#include <unit_effect_rules.h>
#include <unit_production_cost_rules.h>

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

constexpr char kProviderId[]           = "aeshur.hoplite-loyalty";
constexpr char kLoyaltyRuleId[]        = "hoplite-loyalty";
constexpr char kProductionCostRuleId[] = "hoplite-production-cost";

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

class GreekHopliteTrainingPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto effect_version =
            ResolveHostFunction<ReRevvedUnitEffectRulesAbiVersionFn>(
                "ReRevvedUnitEffectRulesAbiVersion");
        const auto register_effect =
            ResolveHostFunction<ReRevvedRegisterUnitEffectRuleFn>(
                "ReRevvedRegisterUnitEffectRule");
        const auto production_cost_version =
            ResolveHostFunction<ReRevvedUnitProductionCostRulesAbiVersionFn>(
                "ReRevvedUnitProductionCostRulesAbiVersion");
        const auto register_production_cost =
            ResolveHostFunction<ReRevvedRegisterUnitProductionCostRuleFn>(
                "ReRevvedRegisterUnitProductionCostRule");
        if (!effect_version || !register_effect || !production_cost_version ||
            !register_production_cost ||
            effect_version() != REREVVED_UNIT_EFFECT_RULES_ABI_VERSION ||
            production_cost_version() !=
                REREVVED_UNIT_PRODUCTION_COST_RULES_ABI_VERSION)
        {
            return;
        }

        ReRevvedUnitEffectRule loyalty{};
        loyalty.struct_size    = sizeof(loyalty);
        loyalty.civilization   = REREVVED_CIVILIZATION_GREEK;
        loyalty.base_unit_type = REREVVED_UNIT_TYPE_PHALANX;
        loyalty.identity       = REREVVED_UNIT_IDENTITY_HOPLITE;
        loyalty.effect         = REREVVED_UNIT_EFFECT_CREATION_LOYALTY;
        std::memcpy(loyalty.provider_id, kProviderId, sizeof(kProviderId));
        std::memcpy(loyalty.rule_id,
                    kLoyaltyRuleId,
                    sizeof(kLoyaltyRuleId));
        register_effect(&loyalty);

        ReRevvedUnitProductionCostRule production_cost{};
        production_cost.struct_size      = sizeof(production_cost);
        production_cost.civilization     = REREVVED_CIVILIZATION_GREEK;
        production_cost.base_unit_type   = REREVVED_UNIT_TYPE_PHALANX;
        production_cost.identity         = REREVVED_UNIT_IDENTITY_HOPLITE;
        production_cost.percentage_delta = -33;
        std::memcpy(production_cost.provider_id,
                    kProviderId,
                    sizeof(kProviderId));
        std::memcpy(production_cost.rule_id,
                    kProductionCostRuleId,
                    sizeof(kProductionCostRuleId));
        register_production_cost(&production_cost);
    }
};

} // namespace

extern "C" REX_MOD_PLUGIN_EXPORT uint32_t rex_mod_abi_version()
{
    return rex::system::kModPluginAbiVersion;
}

extern "C" REX_MOD_PLUGIN_EXPORT rex::system::IModPlugin* rex_mod_create(
    uint32_t abi_version,
    const rex::system::ModHostContext* context)
{
    if (abi_version != rex::system::kModPluginAbiVersion || !context ||
        context->struct_size < sizeof(rex::system::ModHostContext))
    {
        return nullptr;
    }
    return new GreekHopliteTrainingPlugin();
}
