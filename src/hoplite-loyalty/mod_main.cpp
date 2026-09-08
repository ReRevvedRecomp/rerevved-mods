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
Function resolveHostFunction(const char* name)
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
        const auto effectVersion =
            resolveHostFunction<UnitEffectRulesAbiVersionFn>(
                "UnitEffectRulesAbiVersion");
        const auto registerEffect =
            resolveHostFunction<RegisterUnitEffectRuleFn>(
                "RegisterUnitEffectRule");
        const auto productionCostVersion =
            resolveHostFunction<UnitProductionCostRulesAbiVersionFn>(
                "UnitProductionCostRulesAbiVersion");
        const auto registerProductionCost =
            resolveHostFunction<RegisterUnitProductionCostRuleFn>(
                "RegisterUnitProductionCostRule");
        if (!effectVersion || !registerEffect || !productionCostVersion ||
            !registerProductionCost ||
            effectVersion() != UNIT_EFFECT_RULES_ABI_VERSION ||
            productionCostVersion() !=
                UNIT_PRODUCTION_COST_RULES_ABI_VERSION)
        {
            return;
        }

        UnitEffectRule loyalty{};
        loyalty.structSize   = sizeof(loyalty);
        loyalty.civilization = CIVILIZATION_GREEK;
        loyalty.baseUnitType = UNIT_TYPE_PHALANX;
        loyalty.identity     = UNIT_IDENTITY_HOPLITE;
        loyalty.effect       = UNIT_EFFECT_CREATION_LOYALTY;
        std::memcpy(loyalty.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(loyalty.ruleId,
                    kLoyaltyRuleId,
                    sizeof(kLoyaltyRuleId));
        registerEffect(&loyalty);

        UnitProductionCostRule productionCost{};
        productionCost.structSize      = sizeof(productionCost);
        productionCost.civilization    = CIVILIZATION_GREEK;
        productionCost.baseUnitType    = UNIT_TYPE_PHALANX;
        productionCost.identity        = UNIT_IDENTITY_HOPLITE;
        productionCost.percentageDelta = -33;
        std::memcpy(productionCost.providerId,
                    kProviderId,
                    sizeof(kProviderId));
        std::memcpy(productionCost.ruleId,
                    kProductionCostRuleId,
                    sizeof(kProductionCostRuleId));
        registerProductionCost(&productionCost);
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
    return new GreekHopliteTrainingPlugin();
}
