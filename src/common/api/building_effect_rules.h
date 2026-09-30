// Public C ABI for the Chinese Library fixed-gold effect.
// ABI 1 supports stateless previews. Valid runtime registration returns
// ERR_UNAVAILABLE and retains no rule.

#pragma once

#include <stdint.h>

#include <game_ids.h>

#if defined(BUILDING_EFFECT_RULES_API_EXPORTS)
#if defined(_WIN32)
#define BUILDING_EFFECT_RULES_API __declspec(dllexport)
#else
#define BUILDING_EFFECT_RULES_API __attribute__((visibility("default")))
#endif
#else
#define BUILDING_EFFECT_RULES_API
#endif

#define BUILDING_EFFECT_RULES_ABI_VERSION 1u
#define BUILDING_EFFECT_RULE_ID_CAPACITY  64u

enum
{
    BUILDING_EFFECT_RULES_OK                   = 0,
    BUILDING_EFFECT_RULES_ERR_INVALID_ARGUMENT = -10,
    BUILDING_EFFECT_RULES_ERR_BUFFER_TOO_SMALL = -11,
    BUILDING_EFFECT_RULES_ERR_UNAVAILABLE      = -14,
};

typedef int32_t BuildingEffectId;

enum
{
    BUILDING_EFFECT_CHINESE_LIBRARY_FIXED_GOLD = 1, // Preserve science; add 1 final Gold per city turn.
};

enum
{
    BUILDING_EFFECT_PREVIEW_MATCHED  = 1u << 0,
    BUILDING_EFFECT_PREVIEW_OVERFLOW = 1u << 1,
};

typedef struct BuildingEffectRule
{
    uint32_t         structSize;
    char             providerId[BUILDING_EFFECT_RULE_ID_CAPACITY];
    char             ruleId[BUILDING_EFFECT_RULE_ID_CAPACITY];
    BuildingEffectId effect;
    int32_t          reserved[6];
} BuildingEffectRule;

typedef struct BuildingEffectSupport
{
    uint32_t structSize;
    uint32_t runtimeAvailable; // Zero: registration rejects the effect without retaining a rule.
    int32_t  reserved[6];
} BuildingEffectSupport;

// Hypothetical inputs, not live city state. Yields must fit signed 16 bits.
typedef struct BuildingEffectPreviewQuery
{
    uint32_t       structSize;
    CivilizationId civilization; // Current city owner's civilization.
    uint32_t       hasLibrary;   // Exactly 0 or 1.
    int32_t        nativeGold;   // After all native modifiers and overrides.
    int32_t        nativeScience;
    int32_t        reserved[3];
} BuildingEffectPreviewQuery;

typedef struct BuildingEffectPreview
{
    uint32_t structSize;
    int32_t  nativeGold;
    int32_t  finalGold;
    int32_t  nativeScience;
    int32_t  finalScience;
    uint32_t statusFlags;
    int32_t  reserved[2];
} BuildingEffectPreview;

typedef uint32_t (*BuildingEffectRulesAbiVersionFn)(void);
typedef int32_t (*GetBuildingEffectSupportFn)(BuildingEffectSupport* out, uint32_t outSize);
typedef int32_t (*RegisterBuildingEffectRuleFn)(const BuildingEffectRule* rule);
typedef int32_t (*PreviewBuildingEffectFn)(const BuildingEffectRule* rule, const BuildingEffectPreviewQuery* query, BuildingEffectPreview* out, uint32_t outSize);

// Requests require their full size, zero reserved fields, and NUL-terminated
// lowercase provider/rule IDs. Outputs require at least 32 bytes. Preview is
// stateless and does not register, read, or mutate gameplay. See the API guide.
#ifdef __cplusplus
extern "C"
{
#endif
    BUILDING_EFFECT_RULES_API uint32_t BuildingEffectRulesAbiVersion(void);
    BUILDING_EFFECT_RULES_API int32_t  GetBuildingEffectSupport(BuildingEffectSupport* out, uint32_t outSize);
    BUILDING_EFFECT_RULES_API int32_t  RegisterBuildingEffectRule(const BuildingEffectRule* rule);
    BUILDING_EFFECT_RULES_API int32_t  PreviewBuildingEffect(const BuildingEffectRule* rule, const BuildingEffectPreviewQuery* query, BuildingEffectPreview* out, uint32_t outSize);
#ifdef __cplusplus
}
#endif

#undef BUILDING_EFFECT_RULES_API
