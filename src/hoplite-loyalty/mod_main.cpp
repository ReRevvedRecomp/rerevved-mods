#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <unit_effect_rules.h>
#include <unit_production_cost_rules.h>

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

class HopliteLoyaltyPlugin final : public rex::system::IModPlugin
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
        const auto textVersion =
            resolveHostFunction<NationSelectTextAbiVersionFn>(
                "NationSelectTextAbiVersion");
        const auto registerNationSelectText =
            resolveHostFunction<RegisterNationSelectTextRuleFn>(
                "RegisterNationSelectTextRule");
        if (!effectVersion || !registerEffect || !productionCostVersion ||
            !registerProductionCost || !textVersion ||
            !registerNationSelectText ||
            effectVersion() != UNIT_EFFECT_RULES_ABI_VERSION ||
            productionCostVersion() !=
                UNIT_PRODUCTION_COST_RULES_ABI_VERSION)
        {
            return;
        }
        if (textVersion() != NATION_SELECT_TEXT_ABI_VERSION)
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
        if (registerEffect(&loyalty) != UNIT_EFFECT_RULES_OK)
        {
            return;
        }

        UnitProductionCostRule productionCost{};
        productionCost.structSize      = sizeof(productionCost);
        productionCost.civilization    = CIVILIZATION_GREEK;
        productionCost.baseUnitType    = UNIT_TYPE_PHALANX;
        productionCost.identity        = UNIT_IDENTITY_HOPLITE;
        productionCost.percentageDelta = -30;
        std::memcpy(productionCost.providerId,
                    kProviderId,
                    sizeof(kProviderId));
        std::memcpy(productionCost.ruleId,
                    kProductionCostRuleId,
                    sizeof(kProductionCostRuleId));
        if (registerProductionCost(&productionCost) !=
            UNIT_PRODUCTION_COST_RULES_OK)
        {
            return;
        }

        NationSelectTextRule text{};
        text.structSize              = sizeof(text);
        text.surface                 = NATION_SELECT_TEXT_SURFACE_UNIQUE_UNIT;
        text.civilization            = CIVILIZATION_GREEK;
        text.unlockEra               = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.ability                 = 0;
        text.baseUnitType            = UNIT_TYPE_PHALANX;
        text.identity                = UNIT_IDENTITY_HOPLITE;
        text.displayForm             = UNIT_DISPLAY_FORM_UNIT;
        constexpr char kTextRuleId[] = "hoplite-loyalty-text";
        constexpr char kText[] =
            "Hoplite - Starts with Loyalty; costs 10 Production";
        std::memcpy(text.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(text.ruleId, kTextRuleId, sizeof(kTextRuleId));
        std::memcpy(text.text, kText, sizeof(kText));
        const int32_t textResult = registerNationSelectText(&text);
        if (textResult != NATION_SELECT_TEXT_OK)
        {
            std::fprintf(stderr, "Hoplite Loyalty: nation select text registration rejected (%" PRId32 "); gameplay rules remain registered.\n", textResult);
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
    return new HopliteLoyaltyPlugin();
}
