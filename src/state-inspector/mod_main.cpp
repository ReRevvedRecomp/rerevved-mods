#include <rex/system/mod_plugin.h>
#include <rex/ui/imgui_dialog.h>
#include <rex/ui/keybinds.h>

#include <imgui.h>

#include <gameplay_state.h>

#include <cinttypes>
#include <cstdint>
#include <memory>

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

constexpr char kBindName[] = "bind_state_inspector";

template <typename Function>
Function resolveHostFunction(const char* name)
{
#if defined(_WIN32)
    const HMODULE host = GetModuleHandleW(nullptr);
    return host ? reinterpret_cast<Function>(GetProcAddress(host, name))
                : nullptr;
#else
    return reinterpret_cast<Function>(dlsym(RTLD_DEFAULT, name));
#endif
}

struct GameplayApi
{
    GameplayAbiVersionFn version =
        resolveHostFunction<GameplayAbiVersionFn>(
            "GameplayAbiVersion");
    GetGameplayStateFn getState =
        resolveHostFunction<GetGameplayStateFn>(
            "GetGameplayState");
};

const char* yesNo(int value)
{
    return value ? "yes" : "no";
}

const char* knownUnknown(bool known)
{
    return known ? "known" : "unknown";
}

class StateInspectorDialog final : public rex::ui::ImGuiDialog
{
public:
    StateInspectorDialog(rex::ui::ImGuiDrawer* drawer, const GameplayApi& api)
    : ImGuiDialog(drawer)
    , api(api)
    {
    }

    void ToggleVisible()
    {
        visible = !visible;
    }

protected:
    void OnDraw(ImGuiIO&) override
    {
        if (!visible)
        {
            return;
        }

        ImGui::SetNextWindowSize(ImVec2(430.0f, 260.0f), ImGuiCond_FirstUseEver);
        if (!ImGui::Begin("State Inspector##rerevved", &visible, ImGuiWindowFlags_NoCollapse))
        {
            ImGui::End();
            return;
        }

        drawState();
        ImGui::End();
    }

private:
    void drawState() const
    {
        if (!api.version || !api.getState)
        {
            ImGui::TextUnformatted("ReRevved gameplay API is not available.");
            return;
        }

        const uint32_t version = api.version();
        if (version != GAMEPLAY_ABI_VERSION)
        {
            ImGui::Text("Gameplay API mismatch: host %" PRIu32 ", mod %u", version, GAMEPLAY_ABI_VERSION);
            return;
        }

        GameplayState state{};
        const int     result = api.getState(&state, sizeof(state));
        if (result == GAMEPLAY_ERR_UNAVAILABLE)
        {
            ImGui::TextUnformatted("Waiting for the first gameplay frame.");
            return;
        }
        if (result != GAMEPLAY_OK)
        {
            ImGui::Text("Gameplay API error: %d", result);
            return;
        }

        const bool frontendKnown =
            (state.validFields & GAMEPLAY_VALID_FRONTEND) != 0;
        const bool interfaceKnown =
            (state.validFields & GAMEPLAY_VALID_INTERFACE) != 0;
        const bool turnKnown =
            (state.validFields & GAMEPLAY_VALID_TURN) != 0;

        ImGui::Text("Frame sequence: %" PRIu64, state.frameSequence);
        ImGui::Text("Available: %s", yesNo(state.available));
        ImGui::Separator();
        ImGui::Text("Frontend: %s", knownUnknown(frontendKnown));
        if (frontendKnown)
        {
            ImGui::SameLine();
            ImGui::Text("(gameplay %s)", yesNo(state.gameplayActive));
        }
        ImGui::Text("Interface: %s", knownUnknown(interfaceKnown));
        if (interfaceKnown)
        {
            ImGui::SameLine();
            ImGui::Text("(updates %s)", yesNo(state.interfaceUpdate));
        }
        ImGui::Text("Turn owner: %s", knownUnknown(turnKnown));
        if (turnKnown)
        {
            ImGui::Text("Active player: %d", state.activePlayer);
            ImGui::Text("Human player mask: 0x%08" PRIX32, state.humanPlayerMask);
            ImGui::Text("Human turn: %s", yesNo(state.humanTurn));
        }
    }

    GameplayApi api;
    bool        visible = false;
};

class StateInspectorPlugin final : public rex::system::IModPlugin
{
public:
    ~StateInspectorPlugin() override
    {
        shutdown();
    }

    void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override
    {
        dialog = std::make_unique<StateInspectorDialog>(drawer, api);
        rex::ui::RegisterBind(kBindName, "F6", "Toggle ReRevved state inspector", [this]
                              {
                                  if (dialog)
                                  {
                                      dialog->ToggleVisible();
                                  }
                              });
        bindRegistered = true;
    }

    void OnShutdown() override
    {
        shutdown();
    }

private:
    void shutdown()
    {
        if (bindRegistered)
        {
            rex::ui::UnregisterBind(kBindName);
            bindRegistered = false;
        }
        dialog.reset();
    }

    GameplayApi                           api;
    std::unique_ptr<StateInspectorDialog> dialog;
    bool                                  bindRegistered = false;
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
    return new StateInspectorPlugin();
}
