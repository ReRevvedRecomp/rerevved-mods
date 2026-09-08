#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <unit_combat_rules.h>

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

constexpr char kProviderId[] = "aeshur.jaguar-woodsman";

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

bool registerWoodsmanRule(RegisterUnitCombatRuleFn registerRule,
                          const char*              ruleId,
                          UnitCombatProperty       property)
{
    UnitCombatRule rule{};
    rule.structSize      = sizeof(rule);
    rule.civilization    = CIVILIZATION_AZTEC;
    rule.baseUnitType    = UNIT_TYPE_WARRIOR;
    rule.identity        = UNIT_IDENTITY_JAGUAR_WARRIOR;
    rule.terrain         = TERRAIN_FOREST;
    rule.property        = property;
    rule.percentageDelta = 50;
    std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
    std::memcpy(rule.ruleId, ruleId, std::strlen(ruleId) + 1);
    return registerRule(&rule) == UNIT_COMBAT_RULES_OK;
}

class JaguarWoodsmanPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            resolveHostFunction<UnitCombatRulesAbiVersionFn>(
                "UnitCombatRulesAbiVersion");
        const auto registerRule =
            resolveHostFunction<RegisterUnitCombatRuleFn>(
                "RegisterUnitCombatRule");
        const auto textVersion =
            resolveHostFunction<NationSelectTextAbiVersionFn>(
                "NationSelectTextAbiVersion");
        const auto registerNationSelectText =
            resolveHostFunction<RegisterNationSelectTextRuleFn>(
                "RegisterNationSelectTextRule");
        if (!version || !registerRule || !textVersion ||
            !registerNationSelectText ||
            version() != UNIT_COMBAT_RULES_ABI_VERSION)
        {
            return;
        }
        if (textVersion() != NATION_SELECT_TEXT_ABI_VERSION)
        {
            return;
        }

        if (!registerWoodsmanRule(registerRule,
                                  "jaguar-warrior-forest-attack",
                                  UNIT_COMBAT_ATTACK) ||
            !registerWoodsmanRule(registerRule,
                                  "jaguar-warrior-forest-defense",
                                  UNIT_COMBAT_DEFENSE))
        {
            return;
        }

        NationSelectTextRule text{};
        text.structSize              = sizeof(text);
        text.surface                 = NATION_SELECT_TEXT_SURFACE_UNIQUE_UNIT;
        text.civilization            = CIVILIZATION_AZTEC;
        text.unlockEra               = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.ability                 = 0;
        text.baseUnitType            = UNIT_TYPE_WARRIOR;
        text.identity                = UNIT_IDENTITY_JAGUAR_WARRIOR;
        text.displayForm             = UNIT_DISPLAY_FORM_UNIT;
        constexpr char kTextRuleId[] = "jaguar-woodsman-text";
        constexpr char kText[] =
            "Jaguar Warrior - Warrior with +50% Attack and Defense in Forest";
        std::memcpy(text.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(text.ruleId, kTextRuleId, sizeof(kTextRuleId));
        std::memcpy(text.text, kText, sizeof(kText));
        (void)registerNationSelectText(&text);
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
    return new JaguarWoodsmanPlugin();
}
