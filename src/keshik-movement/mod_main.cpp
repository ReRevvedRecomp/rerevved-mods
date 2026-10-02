#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <unit_movement_rules.h>

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

constexpr char kProviderId[] = "aeshur.keshik-movement";
constexpr char kRuleId[]     = "keshik-movement";

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

class KeshikMovementPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version = resolveHostFunction<
            UnitMovementRulesAbiVersionFn>(
            "UnitMovementRulesAbiVersion");
        const auto registerRule = resolveHostFunction<
            RegisterUnitMovementRuleFn>(
            "RegisterUnitMovementRule");
        const auto textVersion = resolveHostFunction<
            NationSelectTextAbiVersionFn>(
            "NationSelectTextAbiVersion");
        const auto registerNationSelectText = resolveHostFunction<
            RegisterNationSelectTextRuleFn>(
            "RegisterNationSelectTextRule");
        if (!version || !registerRule || !textVersion ||
            !registerNationSelectText ||
            version() != UNIT_MOVEMENT_RULES_ABI_VERSION ||
            textVersion() != NATION_SELECT_TEXT_ABI_VERSION)
        {
            return;
        }

        UnitMovementRule rule{};
        rule.structSize   = sizeof(rule);
        rule.civilization = CIVILIZATION_MONGOLIAN;
        rule.baseUnitType = UNIT_TYPE_HORSEMEN;
        rule.identity     = UNIT_IDENTITY_KESHIK;
        rule.value        = 1;
        std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.ruleId, kRuleId, sizeof(kRuleId));
        if (registerRule(&rule) != UNIT_MOVEMENT_RULES_OK)
        {
            return;
        }

        NationSelectTextRule text{};
        text.structSize              = sizeof(text);
        text.surface                 = NATION_SELECT_TEXT_SURFACE_UNIQUE_UNIT;
        text.civilization            = CIVILIZATION_MONGOLIAN;
        text.unlockEra               = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.ability                 = 0;
        text.baseUnitType            = UNIT_TYPE_HORSEMEN;
        text.identity                = UNIT_IDENTITY_KESHIK;
        text.displayForm             = UNIT_DISPLAY_FORM_UNIT;
        constexpr char kTextRuleId[] = "keshik-movement-text";
        constexpr char kText[]       = "Keshik - Horseman with +1 movement";
        std::memcpy(text.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(text.ruleId, kTextRuleId, sizeof(kTextRuleId));
        std::memcpy(text.text, kText, sizeof(kText));
        const int32_t textResult = registerNationSelectText(&text);
        if (textResult != NATION_SELECT_TEXT_OK)
        {
            std::fprintf(stderr, "Keshik Movement: nation select text registration rejected (%" PRId32 "); gameplay rule remains registered.\n", textResult);
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
    return new KeshikMovementPlugin();
}
