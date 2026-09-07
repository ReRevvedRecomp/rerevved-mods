#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <unit_movement_rules.h>

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

constexpr char kProviderId[] = "aeshur.keshik-movement";
constexpr char kRuleId[]     = "keshik-movement";

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

class MongolKeshikMovementPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version = ResolveHostFunction<
            ReRevvedUnitMovementRulesAbiVersionFn>(
            "ReRevvedUnitMovementRulesAbiVersion");
        const auto register_rule = ResolveHostFunction<
            ReRevvedRegisterUnitMovementRuleFn>(
            "ReRevvedRegisterUnitMovementRule");
        const auto presentation_version = ResolveHostFunction<
            ReRevvedNationSelectTextAbiVersionFn>(
            "ReRevvedNationSelectTextAbiVersion");
        const auto register_text = ResolveHostFunction<
            ReRevvedRegisterNationSelectTextRuleFn>(
            "ReRevvedRegisterNationSelectTextRule");
        if (!version || !register_rule || !presentation_version ||
            !register_text ||
            version() != REREVVED_UNIT_MOVEMENT_RULES_ABI_VERSION ||
            presentation_version() != REREVVED_NATION_SELECT_TEXT_ABI_VERSION)
        {
            return;
        }

        ReRevvedUnitMovementRule rule{};
        rule.struct_size    = sizeof(rule);
        rule.civilization   = REREVVED_CIVILIZATION_MONGOLIAN;
        rule.base_unit_type = REREVVED_UNIT_TYPE_HORSEMEN;
        rule.identity       = REREVVED_UNIT_IDENTITY_KESHIK;
        rule.value          = 1;
        std::memcpy(rule.provider_id, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.rule_id, kRuleId, sizeof(kRuleId));
        if (register_rule(&rule) != REREVVED_UNIT_MOVEMENT_RULES_OK)
        {
            return;
        }

        ReRevvedNationSelectTextRule text{};
        text.struct_size             = sizeof(text);
        text.surface                 = REREVVED_NATION_SELECT_TEXT_SURFACE_UNIQUE_UNIT;
        text.civilization            = REREVVED_CIVILIZATION_MONGOLIAN;
        text.unlock_era              = REREVVED_NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.ability                 = 0;
        text.base_unit_type          = REREVVED_UNIT_TYPE_HORSEMEN;
        text.identity                = REREVVED_UNIT_IDENTITY_KESHIK;
        text.display_form            = REREVVED_UNIT_DISPLAY_FORM_UNIT;
        constexpr char kTextRuleId[] = "keshik-movement-text";
        constexpr char kText[]       = "Keshik - Horseman with +1 movement";
        std::memcpy(text.provider_id, kProviderId, sizeof(kProviderId));
        std::memcpy(text.rule_id, kTextRuleId, sizeof(kTextRuleId));
        std::memcpy(text.text, kText, sizeof(kText));
        register_text(&text);
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
    return new MongolKeshikMovementPlugin();
}
