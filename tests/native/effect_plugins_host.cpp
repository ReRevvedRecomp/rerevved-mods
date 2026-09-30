#include <rex/system/mod_plugin.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#define HOST_EXPORT __declspec(dllexport)
#else
#include <dlfcn.h>
#define HOST_EXPORT __attribute__((visibility("default")))
#endif

#if !defined(USE_TITLE_API)
struct WonderEffectSupport;
struct BuildingEffectSupport;
struct WonderEffectRule;
struct BuildingEffectRule;
#if !defined(OMIT_VERSION)
extern "C" HOST_EXPORT uint32_t WonderEffectRulesAbiVersion();
extern "C" HOST_EXPORT uint32_t BuildingEffectRulesAbiVersion();
#endif
#if !defined(OMIT_SUPPORT)
extern "C" HOST_EXPORT int32_t GetWonderEffectSupport(WonderEffectSupport*, uint32_t);
extern "C" HOST_EXPORT int32_t GetBuildingEffectSupport(BuildingEffectSupport*, uint32_t);
#endif
#if !defined(OMIT_REGISTRATION)
extern "C" HOST_EXPORT int32_t RegisterWonderEffectRule(const WonderEffectRule*);
extern "C" HOST_EXPORT int32_t RegisterBuildingEffectRule(const BuildingEffectRule*);
#endif
#endif

#include <building_effect_rules.h>
#include <wonder_effect_rules.h>

namespace
{

std::string mode;
bool        validRequests = true;

struct Calls
{
    unsigned versions      = 0;
    unsigned supports      = 0;
    unsigned registrations = 0;
};

Calls wonderCalls;
Calls buildingCalls;

bool check(bool condition, const char* message)
{
    if (!condition)
    {
        std::fprintf(stderr, "Host check failed: %s\n", message);
    }
    return condition;
}

template <typename Support>
int32_t getSupport(Support* out, uint32_t outSize, Calls& calls)
{
    ++calls.supports;
    if (!out || outSize != sizeof(Support))
    {
        validRequests = false;
        return -10;
    }
    if (mode == "support-error")
    {
        return -10;
    }
    *out                  = {};
    out->structSize       = mode == "support-small" ? sizeof(Support) - 4 : sizeof(Support);
    out->runtimeAvailable = mode == "unavailable" ? 0 : mode == "support-invalid" ? 2
                                                                                  : 1;
    return 0;
}

template <typename Rule>
int32_t registerRule(const Rule* rule, Calls& calls, int32_t effect, const char* provider, const char* ruleId)
{
    ++calls.registrations;
    Rule expected{};
    expected.structSize = sizeof(expected);
    expected.effect     = effect;
    std::memcpy(expected.providerId, provider, std::strlen(provider) + 1);
    std::memcpy(expected.ruleId, ruleId, std::strlen(ruleId) + 1);
    validRequests = validRequests && rule && std::memcmp(rule, &expected, sizeof(expected)) == 0;
    return mode == "registration-error" ? -10 : mode == "registration-unavailable" ? -14
                                                                                   : 0;
}

bool checkCalls(const Calls& before, const Calls& after)
{
    const bool missing    = mode == "missing";
    const bool hasSupport = !missing && mode != "abi-mismatch";
    const bool registers  = mode == "success" || mode == "registration-error" || mode == "registration-unavailable";
    return check(after.versions - before.versions == (missing ? 0u : 1u), "ABI call ordering") &&
           check(after.supports - before.supports == (hasSupport ? 1u : 0u), "support call ordering") &&
           check(after.registrations - before.registrations == (registers ? 1u : 0u), "registration call ordering");
}

#if defined(_WIN32)
using Module = HMODULE;

Module openModule(const char* path)
{
    return LoadLibraryW(std::filesystem::path(path).c_str());
}

void closeModule(Module module)
{
    FreeLibrary(module);
}

template <typename Function>
Function resolve(Module module, const char* name)
{
    return reinterpret_cast<Function>(GetProcAddress(module, name));
}
#else
using Module = void*;

Module openModule(const char* path)
{
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
}

void closeModule(Module module)
{
    dlclose(module);
}

template <typename Function>
Function resolve(Module module, const char* name)
{
    return reinterpret_cast<Function>(dlsym(module, name));
}
#endif

bool runPlugin(const char* kind, const char* path)
{
    const bool wonder = std::strcmp(kind, "wonder") == 0;
    if (!check(wonder || std::strcmp(kind, "building") == 0, "package selector"))
    {
        return false;
    }
    const Module module = openModule(path);
    if (!check(module != nullptr, "load native package"))
    {
        return false;
    }
    const auto                  abi    = resolve<rex::system::ModAbiVersionFn>(module, "rex_mod_abi_version");
    const auto                  create = resolve<rex::system::ModCreateFn>(module, "rex_mod_create");
    bool                        passed = check(abi && create, "plugin exports");
    rex::system::ModHostContext context{};
    context.struct_size = sizeof(context);
    if (passed)
    {
        passed              = check(abi() == rex::system::kModPluginAbiVersion, "plugin ABI") &&
                              check(create(abi() + 1, &context) == nullptr, "reject incompatible plugin ABI") &&
                              check(create(abi(), nullptr) == nullptr, "reject missing host context");
        context.struct_size = sizeof(context) - 1;
        passed              = passed && check(create(abi(), &context) == nullptr, "reject truncated host context");
        context.struct_size = sizeof(context);
    }
    if (passed)
    {
        const Calls before      = wonder ? wonderCalls : buildingCalls;
        const Calls otherBefore = wonder ? buildingCalls : wonderCalls;
        auto*       plugin      = create(abi(), &context);
        passed                  = check(plugin != nullptr, "create native plugin");
        if (plugin)
        {
            plugin->OnModuleLaunched();
            plugin->OnShutdown();
            delete plugin;
#if !defined(USE_TITLE_API)
            passed                 = passed && checkCalls(before, wonder ? wonderCalls : buildingCalls);
            const Calls otherAfter = wonder ? buildingCalls : wonderCalls;
            passed                 = passed && check(otherBefore.versions == otherAfter.versions &&
                                                         otherBefore.supports == otherAfter.supports &&
                                                         otherBefore.registrations == otherAfter.registrations,
                                                     "package independence");
#endif
        }
    }
    closeModule(module);
    return passed && check(validRequests, "exact semantic rule request");
}

} // namespace

#if !defined(USE_TITLE_API)
#if !defined(OMIT_VERSION)
extern "C" HOST_EXPORT uint32_t WonderEffectRulesAbiVersion()
{
    ++wonderCalls.versions;
    return WONDER_EFFECT_RULES_ABI_VERSION + (mode == "abi-mismatch" ? 1 : 0);
}

extern "C" HOST_EXPORT uint32_t BuildingEffectRulesAbiVersion()
{
    ++buildingCalls.versions;
    return BUILDING_EFFECT_RULES_ABI_VERSION + (mode == "abi-mismatch" ? 1 : 0);
}
#endif

#if !defined(OMIT_SUPPORT)
extern "C" HOST_EXPORT int32_t GetWonderEffectSupport(WonderEffectSupport* out, uint32_t outSize)
{
    return getSupport(out, outSize, wonderCalls);
}

extern "C" HOST_EXPORT int32_t GetBuildingEffectSupport(BuildingEffectSupport* out, uint32_t outSize)
{
    return getSupport(out, outSize, buildingCalls);
}
#endif

#if !defined(OMIT_REGISTRATION)
extern "C" HOST_EXPORT int32_t RegisterWonderEffectRule(const WonderEffectRule* rule)
{
    return registerRule(rule, wonderCalls, WONDER_EFFECT_STONEHENGE_RELIGION_CULTURE, "aeshur.stonehenge-religion", "stonehenge-religion-culture");
}

extern "C" HOST_EXPORT int32_t RegisterBuildingEffectRule(const BuildingEffectRule* rule)
{
    return registerRule(rule, buildingCalls, BUILDING_EFFECT_CHINESE_LIBRARY_FIXED_GOLD, "aeshur.chinese-library-gold", "chinese-library-fixed-gold");
}
#endif
#endif

int main(int argc, char** argv)
{
    if (argc < 4 || argc % 2 != 0)
    {
        std::fprintf(stderr, "Expected: mode (wonder|building plugin-path)+\n");
        return 1;
    }
    mode        = argv[1];
    bool passed = true;
    for (int index = 2; index < argc; index += 2)
    {
        passed = runPlugin(argv[index], argv[index + 1]) && passed;
    }
    return check(passed, "plugin lifecycle") ? 0 : 1;
}
