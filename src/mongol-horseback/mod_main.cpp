#include <rex/system/mod_plugin.h>

#include <nation_select_text.h>
#include <unique_era_abilities.h>

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

constexpr char kProviderId[] = "aeshur.mongol-horseback";
constexpr char kRuleId[]     = "mongol-ancient-horseback-riding";

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

class MongolHorsebackPlugin final : public rex::system::IModPlugin
{
public:
    void OnModuleLaunched() override
    {
        const auto version =
            resolveHostFunction<EraAbilitiesAbiVersionFn>(
                "EraAbilitiesAbiVersion");
        const auto registerRule = resolveHostFunction<
            RegisterEraAbilityReplacementFn>(
            "RegisterEraAbilityReplacement");
        const auto textVersion = resolveHostFunction<
            NationSelectTextAbiVersionFn>(
            "NationSelectTextAbiVersion");
        const auto registerNationSelectText = resolveHostFunction<
            RegisterNationSelectTextRuleFn>(
            "RegisterNationSelectTextRule");
        if (!version || !registerRule || !textVersion ||
            !registerNationSelectText ||
            version() != ERA_ABILITIES_ABI_VERSION ||
            textVersion() != NATION_SELECT_TEXT_ABI_VERSION)
        {
            return;
        }

        EraAbilityReplacement rule{};
        rule.structSize   = sizeof(rule);
        rule.civilization = CIVILIZATION_MONGOLIAN;
        rule.unlockEra    = UNLOCK_ERA_ANCIENT;
        rule.replacementAbility =
            ERA_ABILITY_KNOWLEDGE_OF_HORSEBACK_RIDING;
        std::memcpy(rule.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(rule.ruleId, kRuleId, sizeof(kRuleId));
        if (registerRule(&rule) != ERA_ABILITIES_OK)
        {
            return;
        }

        NationSelectTextRule text{};
        text.structSize   = sizeof(text);
        text.surface      = NATION_SELECT_TEXT_SURFACE_ERA_ABILITY;
        text.civilization = CIVILIZATION_MONGOLIAN;
        text.unlockEra    = UNLOCK_ERA_ANCIENT;
        text.ability =
            ERA_ABILITY_KNOWLEDGE_OF_HORSEBACK_RIDING;
        text.baseUnitType            = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.identity                = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        text.displayForm             = NATION_SELECT_TEXT_SELECTOR_UNUSED;
        constexpr char kTextRuleId[] = "mongol-ancient-horseback-riding-text";
        constexpr char kText[]       = "Knowledge of Horseback Riding";
        std::memcpy(text.providerId, kProviderId, sizeof(kProviderId));
        std::memcpy(text.ruleId, kTextRuleId, sizeof(kTextRuleId));
        std::memcpy(text.text, kText, sizeof(kText));
        const int32_t textResult = registerNationSelectText(&text);
        if (textResult != NATION_SELECT_TEXT_OK)
        {
            std::fprintf(stderr, "Mongol Horseback: nation select text registration rejected (%" PRId32 "); gameplay rule remains registered.\n", textResult);
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
    return new MongolHorsebackPlugin();
}
