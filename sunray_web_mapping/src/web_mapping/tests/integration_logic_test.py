#!/usr/bin/env python3
"""Cross-package checks for Web Mapping integration logic."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_MAIN = ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "web" / "main.js"
WEB_INDEX = ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "web" / "index.html"
WEB_NODE = ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "ros" / "node.py"
BROKER = ROOT / "src" / "web_fast_lio_broker" / "web_fast_lio_broker" / "broker.py"
MID360_WEB_LAUNCH = ROOT / "src" / "web_fast_lio_broker" / "launch" / "mid360_web_mapping.launch.py"
FAST_LIO_LAUNCH = ROOT / "src" / "fast_lio" / "launch" / "mapping.launch.py"
LIVOX_PREVIEW = ROOT / "src" / "web_livox_observer" / "src" / "preview.cpp"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_layer_led_availability_uses_live_topic_state_not_cached_points() -> None:
    main_js = _text(WEB_MAIN)

    assert "button.classList.toggle('is-available', online)" in main_js
    assert "button.classList.toggle('has-cache', hasCachedPoints)" in main_js
    assert "button.disabled = !online && !hasCachedPoints" in main_js
    assert "online || hasCachedPoints" not in main_js


def test_start_acceptance_clears_previous_live_mapping_scene() -> None:
    main_js = _text(WEB_MAIN)

    assert "if (payload.command === 'start')" in main_js
    assert "resetLiveMappingScene()" in main_js
    assert "state.mapping.state = 'starting'" in main_js
    assert "state.mapping.pendingCommand = 'start'" in main_js
    assert "function shouldHoldPendingMappingState(mapping)" in main_js
    assert "function pendingMappingCommandIsSettled(command, mappingState)" in main_js
    assert "clearTrajectory({ clearPose: true, resetCutoff: true })" in main_js
    assert "state.paths[source] = []" in main_js
    assert "optimized: '/web_mapping/current_frame'" in main_js
    assert "optimized: 'corrected_map'" not in main_js


def test_saved_map_preview_clears_and_isolates_live_trajectory() -> None:
    main_js = _text(WEB_MAIN)

    assert "clearTrajectory({ clearPose: true })" in main_js
    assert "payload.type === 'pose' && !state.mapHistory.savedPreviewActive" in main_js
    assert "payload.type === 'path' && !state.mapHistory.savedPreviewActive" in main_js


def test_trajectory_visibility_can_be_toggled_separately_from_layers() -> None:
    main_js = _text(WEB_MAIN)

    assert "trajectoryVisible: true" in main_js
    assert "toggleTrajectoryVisibility" in main_js
    assert "state.trajectoryVisible && state.visibleSources.has('raw')" in main_js
    assert "state.trajectoryVisible && state.visibleSources.has('optimized')" in main_js
    assert "function hasVisibleTrajectory()" in main_js
    assert "ui.clearTrajectory.disabled = !hasVisibleTrajectory()" in main_js


def test_viewport_fps_hud_uses_single_request_animation_frame_loop() -> None:
    index_html = _text(WEB_INDEX)
    main_js = _text(WEB_MAIN)

    assert "<span>渲染</span>" not in index_html
    assert 'class="viewport-file"' in index_html
    assert 'class="viewport-filename"' not in index_html
    assert 'class="viewport-sep"' not in index_html
    assert 'class="viewport-fps"' in index_html
    assert "function startRenderLoop()" in main_js
    assert "if (state.renderLoopRunning) return" in main_js
    assert "function updateRenderFps()" in main_js
    assert "if (elapsed < 200) return" in main_js
    assert "const nextFps = (state.renderFrameCount / elapsed) * 1000" in main_js
    assert "ui.hudFrame.textContent = `FPS ${nextFps.toFixed(0)}`" in main_js
    assert "startRenderLoop()" in main_js


def test_map_library_marks_current_rendered_map_and_gizmo_axes() -> None:
    index_html = _text(WEB_INDEX)
    main_js = _text(WEB_MAIN)

    assert "historyRenderProgress" not in index_html
    assert "historyRenderProgress" not in main_js
    assert "history-inline-progress" in main_js
    assert "head.appendChild(inlineProgress)" in main_js
    assert "item.appendChild(inlineProgress)" not in main_js
    assert "historyProgressHtml(progress)" in main_js
    assert "history-item${rendered ? ' is-rendered' : ''}${progress ? ' is-rendering' : ''}" in main_js
    assert "viewportFileName:" not in main_js
    assert "function currentRenderedMapName()" not in main_js
    assert "function visibleMapLayerSummary()" not in main_js
    assert "function renderedMapSessionId()" in main_js
    assert "activePreviewId" in main_js
    assert "activePreviewName" not in main_js
    assert "history-render-led" in main_js
    assert "history-item${rendered ? ' is-rendered' : ''}" in main_js
    assert "const GIZMO_LABELS" in main_js
    assert "function addGizmoLabels()" in main_js
    assert "createGizmoLabel(label.axis, label.color)" in main_js


def test_map_library_refresh_keeps_sidebar_layout_stable() -> None:
    main_js = _text(WEB_MAIN)
    styles_css = _text(ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "web" / "styles.css")

    assert "renderMapHistory({ loading: true, sessions: state.mapHistory.sessions })" in main_js
    assert "const hasExistingList = ui.historyList.querySelector('.history-item')" in main_js
    assert "if (!hasExistingList)" in main_js
    assert "historySessionHtml(session)" in main_js
    assert "openSessionIds" not in main_js
    assert "const wasSelected = state.mapHistory.selectedSessionId === sessionId" in main_js
    assert "if (row || !wasSelected)" in main_js
    assert "setMapHistoryRefreshState(true)" in main_js
    assert "setMapHistoryRefreshState(false)" in main_js
    assert ".history-refresh:disabled" in styles_css


def test_map_library_exposes_clean_map_diagnostics_and_rerun() -> None:
    index_html = _text(WEB_INDEX)
    main_js = _text(WEB_MAIN)
    styles_css = _text(ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "web" / "styles.css")

    assert "function historyPostprocessHtml(session)" in main_js
    assert "后处理诊断" in main_js
    assert "historyPostprocessSelected" in main_js
    assert "historyPostprocessPreset" in main_js
    assert "POSTPROCESS_PRESETS" in main_js
    assert "syncPostprocessPresetOptions(session)" in main_js
    assert "option.disabled = isCurrent" in main_js
    assert "重跑后处理档位" in index_html
    assert "JSON.stringify({ preset })" in main_js
    assert "POST" in main_js
    assert "/api/maps/postprocess?id=" in main_js
    assert "rerunMapPostprocess" in main_js
    assert ".history-postprocess-summary" in styles_css


def test_stop_waits_for_backend_completion_before_history_refresh() -> None:
    main_js = _text(WEB_MAIN)
    broker = _text(BROKER)

    assert "state.mapHistory.pendingStopRefresh = true" in main_js
    assert "state.mapping.state = 'stopping'" in main_js
    assert "state.mapping.pendingCommand = 'stop'" in main_js
    assert "state.mapping.state = 'stopped'" not in main_js
    assert "state.mapping.state === 'stopped'" in main_js
    assert "handleStopCompleted()" in main_js
    assert "mappingState === 'saving' || mappingState === 'starting'" not in main_js
    assert 'self._message = "正在关闭雷达和 FAST-LIO2，随后运行后处理"' in broker
    assert "self._run_clean_map_postprocess()" in broker
    assert "self._state = \"stopped\"" in broker
    assert "self._stop_fast_lio_process()" in broker
    assert "self._stop_livox_process()" in broker


def test_current_frame_stream_has_no_global_map_stale_fallback() -> None:
    broker = _text(BROKER)

    assert "current_frame_fallback_sec" not in broker
    assert "_current_frame_is_stale" not in broker
    assert "or self._current_frame_is_stale()" not in broker
    assert "fast_lio_raw_cloud_topic" not in broker
    assert "self.accumulated_map_pub.publish(msg)" in broker


def test_web_control_uses_fast_lio_realtime_frame_for_accumulation() -> None:
    launch = _text(MID360_WEB_LAUNCH)

    assert '"optimized_cloud_topic": "/web_mapping/current_frame"' in launch
    assert 'DeclareLaunchArgument("fast_lio_current_frame_topic", default_value="/web_fast_lio/cloud_registered")' in launch
    assert '("/cloud_registered", fast_lio_current_frame_topic)' in launch
    assert '"publish_fast_lio_current_frame": ParameterValue(publish_fast_lio_current_frame, value_type=bool)' in launch


def test_raw_livox_preview_is_limited_separately_from_topic_rate() -> None:
    launch = _text(MID360_WEB_LAUNCH)
    web_launch = _text(ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "launch" / "web_mapping.launch.py")
    node = _text(ROOT / "src" / "web_mapping" / "src" / "web_mapping" / "web_mapping" / "ros" / "node.py")
    cmake = _text(ROOT / "src" / "web_livox_observer" / "CMakeLists.txt")
    preview_node = _text(LIVOX_PREVIEW)

    assert '"raw_cloud_topic": "/web_mapping/raw_cloud"' in launch
    assert '"livox_custom_topic": livox_lidar_topic' in launch
    assert 'executable="web_livox_observer_node"' in launch
    assert '"max_raw_points_per_cloud": 15000' in launch
    assert '"min_raw_cloud_interval_sec": 0.3' in launch
    assert 'DeclareLaunchArgument("min_raw_cloud_interval_sec", default_value="0.5")' in web_launch
    assert "self.min_raw_cloud_interval_sec" in node
    assert "def _cloud_min_interval(self, source: str) -> float:" in node
    assert "def _lidar_status_topic_override(self, payload: dict[str, Any]) -> dict[str, Any]:" in node
    assert "lidar_status_qos = QoSProfile(depth=1)" in node
    assert (
        "self.create_subscription(String, self.lidar_status_topic, self._lidar_status_callback, lidar_status_qos)"
        in node
    )
    assert '"lidar_status_topic": "/web_mapping/lidar_status"' in launch
    assert "add_executable(web_livox_observer_node src/web_livox_observer_node.cpp)" in cmake
    assert "makeRawCloudPreview" in preview_node
    assert "sample_every" in preview_node


def test_web_fast_lio_launch_uses_current_direct_broker() -> None:
    broker = _text(BROKER)
    launch = _text(MID360_WEB_LAUNCH)
    fast_lio_launch = _text(FAST_LIO_LAUNCH)
    main_js = _text(WEB_MAIN)

    assert "web_fast_lio_broker.clean_map_postprocess" in broker
    assert "run_clean_map" in broker
    assert "rerun_postprocess" in broker
    assert "self.raw_livox_topic" in broker
    assert "self.fast_lio_imu_topic" in broker
    assert "self.fast_lio_current_frame_topic" in broker
    assert "self.fast_lio_odom_topic" in broker
    assert '"raw_livox_topic": livox_lidar_topic' in launch
    assert '"fast_lio_odom_topic": fast_lio_odom_topic' in launch
    assert '"fast_lio_map_save_service": fast_lio_map_save_service' in launch
    assert 'DeclareLaunchArgument("fast_lio_odom_topic", default_value="/web_fast_lio/odometry")' in launch
    assert 'DeclareLaunchArgument("fast_lio_map_save_service", default_value="/web_fast_lio/map_save")' in launch
    assert '("/cloud_registered", fast_lio_current_frame_topic)' in launch
    assert '("/Odometry", fast_lio_odom_topic)' in launch
    assert '("map_save", fast_lio_map_save_service)' in launch
    assert "('map_save', map_save_service)" in fast_lio_launch
    assert "('/cloud_registered', cloud_registered_topic)" in fast_lio_launch
    assert "('/Odometry', odometry_topic)" in fast_lio_launch
    assert "if (mappingState === 'error') return state.mapping.message || '建图未启动，请检查雷达和定位数据'" in main_js


def test_websocket_clients_do_not_shadow_rclpy_node_clients() -> None:
    node = _text(WEB_NODE)

    assert "self._websocket_clients" in node
    assert "self._clients:" not in node
    assert "self._clients =" not in node


if __name__ == "__main__":
    test_layer_led_availability_uses_live_topic_state_not_cached_points()
    test_start_acceptance_clears_previous_live_mapping_scene()
    test_saved_map_preview_clears_and_isolates_live_trajectory()
    test_trajectory_visibility_can_be_toggled_separately_from_layers()
    test_viewport_fps_hud_uses_single_request_animation_frame_loop()
    test_map_library_marks_current_rendered_map_and_gizmo_axes()
    test_map_library_refresh_keeps_sidebar_layout_stable()
    test_map_library_exposes_clean_map_diagnostics_and_rerun()
    test_stop_waits_for_backend_completion_before_history_refresh()
    test_current_frame_stream_has_no_global_map_stale_fallback()
    test_web_control_uses_fast_lio_realtime_frame_for_accumulation()
    test_raw_livox_preview_is_limited_separately_from_topic_rate()
    test_web_fast_lio_launch_uses_current_direct_broker()
    test_websocket_clients_do_not_shadow_rclpy_node_clients()
    print("integration logic ok")
