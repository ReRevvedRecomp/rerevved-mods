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
Function ResolveHostFunction(const char* name)
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
    ReRevvedGameplayAbiVersionFn version =
        ResolveHostFunction<ReRevvedGameplayAbiVersionFn>(
            "ReRevvedGameplayAbiVersion");
    ReRevvedGetGameplayStateFn get_state =
        ResolveHostFunction<ReRevvedGetGameplayStateFn>(
            "ReRevvedGetGameplayState");
};

const char* YesNo(int value)
{
    return value ? "yes" : "no";
}

const char* KnownUnknown(bool known)
{
    return known ? "known" : "unknown";
}

class StateInspectorDialog final : public rex::ui::ImGuiDialog
{
public:
    StateInspectorDialog(rex::ui::ImGuiDrawer* drawer, const GameplayApi& api)
    : ImGuiDialog(drawer)
    , api_(api)
    {
    }

    void ToggleVisible()
    {
        visible_ = !visible_;
    }

protected:
    void OnDraw(ImGuiIO&) override
    {
        if (!visible_)
        {
            return;
        }

        ImGui::SetNextWindowSize(ImVec2(430.0f, 260.0f), ImGuiCond_FirstUseEver);
        if (!ImGui::Begin("State Inspector##rerevved", &visible_, ImGuiWindowFlags_NoCollapse))
        {
            ImGui::End();
            return;
        }

        DrawState();
        ImGui::End();
    }

private:
    void DrawState() const
    {
        if (!api_.version || !api_.get_state)
        {
            ImGui::TextUnformatted("ReRevved gameplay API is not available.");
            return;
        }

        const uint32_t version = api_.version();
        if (version != REREVVED_GAMEPLAY_ABI_VERSION)
        {
            ImGui::Text("Gameplay API mismatch: host %" PRIu32 ", mod %u", version, REREVVED_GAMEPLAY_ABI_VERSION);
            return;
        }

        ReRevvedGameplayState state{};
        const int             result = api_.get_state(&state, sizeof(state));
        if (result == REREVVED_GAMEPLAY_ERR_UNAVAILABLE)
        {
            ImGui::TextUnformatted("Waiting for the first gameplay frame.");
            return;
        }
        if (result != REREVVED_GAMEPLAY_OK)
        {
            ImGui::Text("Gameplay API error: %d", result);
            return;
        }

        const bool frontend_known =
            (state.valid_fields & REREVVED_GAMEPLAY_VALID_FRONTEND) != 0;
        const bool interface_known =
            (state.valid_fields & REREVVED_GAMEPLAY_VALID_INTERFACE) != 0;
        const bool turn_known =
            (state.valid_fields & REREVVED_GAMEPLAY_VALID_TURN) != 0;

        ImGui::Text("Frame sequence: %" PRIu64, state.frame_sequence);
        ImGui::Text("Available: %s", YesNo(state.available));
        ImGui::Separator();
        ImGui::Text("Frontend: %s", KnownUnknown(frontend_known));
        if (frontend_known)
        {
            ImGui::SameLine();
            ImGui::Text("(gameplay %s)", YesNo(state.gameplay_active));
        }
        ImGui::Text("Interface: %s", KnownUnknown(interface_known));
        if (interface_known)
        {
            ImGui::SameLine();
            ImGui::Text("(updates %s)", YesNo(state.interface_update));
        }
        ImGui::Text("Turn owner: %s", KnownUnknown(turn_known));
        if (turn_known)
        {
            ImGui::Text("Active player: %d", state.active_player);
            ImGui::Text("Human player mask: 0x%08" PRIX32, state.human_player_mask);
            ImGui::Text("Human turn: %s", YesNo(state.human_turn));
        }
    }

    GameplayApi api_;
    bool        visible_ = false;
};

class StateInspectorPlugin final : public rex::system::IModPlugin
{
public:
    ~StateInspectorPlugin() override
    {
        Shutdown();
    }

    void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override
    {
        dialog_ = std::make_unique<StateInspectorDialog>(drawer, api_);
        rex::ui::RegisterBind(kBindName, "F6", "Toggle ReRevved state inspector", [this]
                              {
                                  if (dialog_)
                                  {
                                      dialog_->ToggleVisible();
                                  }
                              });
        bind_registered_ = true;
    }

    void OnShutdown() override
    {
        Shutdown();
    }

private:
    void Shutdown()
    {
        if (bind_registered_)
        {
            rex::ui::UnregisterBind(kBindName);
            bind_registered_ = false;
        }
        dialog_.reset();
    }

    GameplayApi                           api_;
    std::unique_ptr<StateInspectorDialog> dialog_;
    bool                                  bind_registered_ = false;
};

} // namespace

extern "C" REX_MOD_PLUGIN_EXPORT uint32_t rex_mod_abi_version()
{
    return rex::system::kModPluginAbiVersion;
}

extern "C" REX_MOD_PLUGIN_EXPORT rex::system::IModPlugin* rex_mod_create(
    uint32_t                           abi_version,
    const rex::system::ModHostContext* context)
{
    if (abi_version != rex::system::kModPluginAbiVersion || !context ||
        context->struct_size < sizeof(rex::system::ModHostContext))
    {
        return nullptr;
    }
    return new StateInspectorPlugin();
}
