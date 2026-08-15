import * as THREE from './vendor/three.module.js'
import { OrbitControls } from './vendor/OrbitControls.js'

const canvas = document.querySelector('#pointCanvas')
const viewportPanel = document.querySelector('.viewport-panel')
const params = new URLSearchParams(window.location.search)

const ui = {
  wsState: document.querySelector('#wsState'),
  imuState: document.querySelector('#imuState'),
  poseState: document.querySelector('#poseState'),
  radarDetailState: document.querySelector('#radarDetailState'),
  sensorHealthState: document.querySelector('#sensorHealthState'),
  clientCount: document.querySelector('#clientCount'),
  sensorDataAge: document.querySelector('#sensorDataAge'),
  radarHz: document.querySelector('#radarHz'),
  radarAge: document.querySelector('#radarAge'),
  radarTopic: document.querySelector('#radarTopic'),
  radarPoints: document.querySelector('#radarPoints'),
  webVizState: document.querySelector('#webVizState'),
  webVizHz: document.querySelector('#webVizHz'),
  webVizAge: document.querySelector('#webVizAge'),
  webVizPoints: document.querySelector('#webVizPoints'),
  webVizSourcePoints: document.querySelector('#webVizSourcePoints'),
  poseHz: document.querySelector('#poseHz'),
  poseAge: document.querySelector('#poseAge'),
  poseX: document.querySelector('#poseX'),
  poseY: document.querySelector('#poseY'),
  poseZ: document.querySelector('#poseZ'),
  poseYaw: document.querySelector('#poseYaw'),
  poseFrame: document.querySelector('#poseFrame'),
  imuHz: document.querySelector('#imuHz'),
  imuAge: document.querySelector('#imuAge'),
  imuAccelNorm: document.querySelector('#imuAccelNorm'),
  imuGyroNorm: document.querySelector('#imuGyroNorm'),
  imuFrame: document.querySelector('#imuFrame'),
  hudFrame: document.querySelector('#hudFrame'),
  bufferPoints: document.querySelector('#bufferPoints'),
  mapPoints: document.querySelector('#mapPoints'),
  optimizedPoints: document.querySelector('#optimizedPoints'),
  rawPoints: document.querySelector('#rawPoints'),
  poseReadout: document.querySelector('#poseReadout'),
  imuReadout: document.querySelector('#imuReadout'),
  pointSize: document.querySelector('#pointSize'),
  pointSizeValue: document.querySelector('#pointSizeValue'),
  pointBudget: document.querySelector('#pointBudget'),
  pointBudgetValue: document.querySelector('#pointBudgetValue'),
  clearCloud: document.querySelector('#clearCloud'),
  layerSettingsToggle: document.querySelector('#layerSettingsToggle'),
  layerSettingsPopover: document.querySelector('#layerSettingsPopover'),
  resetView: document.querySelector('#resetView'),
  followPose: document.querySelector('#followPose'),
  toggleTrajectory: document.querySelector('#toggleTrajectory'),
  clearTrajectory: document.querySelector('#clearTrajectory'),
  mappingState: document.querySelector('#mappingState'),
  mappingMessage: document.querySelector('#mappingMessage'),
  mappingSessionName: document.querySelector('#mappingSessionName'),
  startLidar: document.querySelector('#startLidar'),
  stopLidar: document.querySelector('#stopLidar'),
  checkLidar: document.querySelector('#checkLidar'),
  startMapping: document.querySelector('#startMapping'),
  stopMapping: document.querySelector('#stopMapping'),
  historySummary: document.querySelector('#historySummary'),
  refreshHistory: document.querySelector('#refreshHistory'),
  historyList: document.querySelector('#historyList'),
  historyPreviewSelected: document.querySelector('#historyPreviewSelected'),
  historyDownloadSelected: document.querySelector('#historyDownloadSelected'),
  historyDeleteSelected: document.querySelector('#historyDeleteSelected'),
  historyPostprocessPreset: document.querySelector('#historyPostprocessPreset'),
  historyPostprocessSelected: document.querySelector('#historyPostprocessSelected'),
  layerToggles: Array.from(document.querySelectorAll('.layer-toggle')),
  sectionToggles: Array.from(document.querySelectorAll('.section-toggle')),
  backendTopicRows: Array.from(document.querySelectorAll('.topic-row')),
}

const SOURCES = ['map', 'optimized', 'raw']
const CLOUD_SOURCES = SOURCES
const SAVED_MAP_SOURCES = ['map', 'optimized']
const UNLIMITED_POINT_BUDGET = 10000000
const DEFAULT_VISIBLE_SOURCES = new Set(['map', 'optimized', 'raw'])
const ACCUMULATING_SOURCES = new Set(['optimized'])
const SOURCE_LABELS = {
  map: '后处理地图',
  optimized: '里程计地图',
  raw: '雷达原始扫描',
}

const MAPPING_STATE_LABELS = {
  idle: 'ready',
  starting: 'starting',
  waiting: 'waiting',
  mapping: 'mapping',
  saving: 'saving',
  stopping: 'stopping',
  stopped: 'stopped',
  error: 'error',
}

const MAPPING_STATE_CLASS = {
  idle: 'is-waiting',
  starting: 'is-waiting',
  waiting: 'is-waiting',
  mapping: 'is-online',
  saving: 'is-waiting',
  stopping: 'is-waiting',
  stopped: 'is-stale',
  error: 'is-disconnected',
}

const SCENE = {
  background: '#050505',
  fog: '#151515',
  coarseGrid: '#242424',
  fineGrid: '#171717',
  path: '#7c8cff',
  optimizedLow: new THREE.Color(0x242424),
  optimizedHigh: new THREE.Color(0xffffff),
  mapLow: new THREE.Color(0x191919),
  mapHigh: new THREE.Color(0xf6f6f6),
  trajectory: new THREE.Color(0x8fa5ff),
}

const GRID_HELPERS = [
  { size: 240, divisions: 240, color: SCENE.fineGrid, z: -0.024, renderOrder: -20 },
  { size: 240, divisions: 48, color: SCENE.coarseGrid, z: -0.016, renderOrder: -10 },
]

const WORLD_AXES = {
  length: 6,
  width: 2,
  radius: 0.024,
  mode: 'mesh',
  zOffset: 0.08,
  renderOrder: 10,
}

const GIZMO_AXES = {
  length: 1.5,
  width: 2,
}

const GIZMO_LABELS = [
  { axis: 'X', position: [1.86, 0, 0], color: '#ff0000' },
  { axis: 'Y', position: [0, 1.86, 0], color: '#00ff00' },
  { axis: 'Z', position: [0, 0, 1.86], color: '#0000ff' },
]

const SAVE_DOWNLOAD_ATTEMPTS = 45
const SAVE_DOWNLOAD_INTERVAL_MS = 1000
const COMMAND_PENDING_TIMEOUT_MS = 12000
const LIVE_STAT_STALE_MS = 2000
const LIDAR_COMMANDS = new Set(['start_lidar', 'stop_lidar', 'check_lidar'])
const MAPPING_COMMANDS = new Set(['start', 'stop'])
const POSTPROCESS_PRESETS = [
  { id: 'light', label: '轻量' },
  { id: 'default', label: '默认' },
  { id: 'detail', label: '细节' },
]

const RAW_COLOR_STOPS = [
  [0.00, new THREE.Color(0x265dff)],
  [0.28, new THREE.Color(0x00d8ff)],
  [0.52, new THREE.Color(0x26e85f)],
  [0.76, new THREE.Color(0xffe447)],
  [1.00, new THREE.Color(0xff3030)],
]

const state = {
  mockMode: params.has('mock'),
  pointSize: Number(ui.pointSize.value),
  pointBudget: Number(ui.pointBudget.value),
  heartbeatTimer: null,
  bridgeConnected: false,
  visibleSources: new Set(DEFAULT_VISIBLE_SOURCES),
  layers: {},
  cloudSeq: 0,
  liveStats: {},
  latestFramePoints: 0,
  renderFrameCount: 0,
  renderFpsLastAt: null,
  renderLoopRunning: false,
  pose: null,
  imu: null,
  paths: {
    raw: [],
    optimized: [],
  },
  pathSourceCounts: {
    raw: 0,
    optimized: 0,
  },
  pathClearSourceCounts: {
    raw: 0,
    optimized: 0,
  },
  bounds: null,
  followPose: false,
  trajectoryVisible: true,
  reconnectTimer: null,
  mockTimer: null,
  mockStartTime: performance.now(),
  mapping: {
    state: 'idle',
    message: '等待开始',
    allowedCommands: ['start_lidar', 'check_lidar'],
    backend: { name: 'stub', available: false },
    lidarState: 'disconnected',
    lidarValid: false,
    lidarChecking: false,
    lidarMessage: '雷达未连接',
    lastCommand: '',
    postprocess: {},
    pendingCommand: '',
    pendingSince: 0,
  },
  topicStats: {},
  mapHistory: {
    loading: false,
    deleting: '',
    previewing: '',
    postprocessing: '',
    renderProgress: {
      visible: false,
      value: 0,
      stage: '等待任务',
      detail: '-',
      status: 'idle',
      fileName: '',
      sessionId: '',
      hideTimer: null,
    },
    stopPreviousLatest: null,
    stopStartedAt: 0,
    pendingStopRefresh: false,
    savedPreviewActive: false,
    activePreviewId: '',
    selectedSessionId: '',
    postprocessPresets: {},
    sessions: [],
  },
}

let ws = null
let renderer = null
let scene = null
let camera = null
let controls = null
let poseGeometry = null
let poseMarker = null
let pathLines = { raw: null, optimized: null }
let pointSprite = null
let gizmoRenderer = null
let gizmoScene = null
let gizmoCamera = null

function initThree() {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false })
  renderer.setClearColor(SCENE.background, 1)
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))

  scene = new THREE.Scene()
  scene.background = new THREE.Color(SCENE.background)
  scene.fog = new THREE.Fog(SCENE.fog, 80, 240)

  camera = new THREE.PerspectiveCamera(45, 1, 0.05, 1200)
  camera.up.set(0, 0, 1)
  camera.position.set(14, 14, 12)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.screenSpacePanning = true
  controls.minPolarAngle = 0.05
  controls.maxPolarAngle = Math.PI / 2 - 0.02
  controls.minDistance = 1.2
  controls.maxDistance = 520
  controls.target.set(0, 0, 0)
  controls.update()
  controls.addEventListener('start', () => {
    if (!state.followPose) return
    state.followPose = false
    updateFollowButton()
  })

  scene.add(new THREE.AmbientLight(0xffffff, 0.75))
  const sun = new THREE.DirectionalLight(0xffffff, 0.7)
  sun.position.set(12, 16, 10)
  scene.add(sun)

  addGroundGrid()
  addAxes(scene, WORLD_AXES)
  pointSprite = getSquarePointSprite()
  createCloudLayers()
  createPoseLayer()
  createGizmo()
  syncLayerButtons()
  resizeRenderer()
}

function addGroundGrid() {
  scene.add(...GRID_HELPERS.map(createGroundGrid))
}

function createGroundGrid({ size, divisions, color, z, renderOrder }) {
  const grid = new THREE.GridHelper(size, divisions, color, color)
  grid.rotation.x = Math.PI / 2
  grid.position.z = z
  grid.renderOrder = renderOrder
  configureHelperMaterials(grid)
  return grid
}

function addAxes(targetScene, { length, width, radius = 0.02, mode = 'line', zOffset = 0, renderOrder = 0 }) {
  const axes = [
    [[0, 0, 0], [length, 0, 0], 0xff3030],
    [[0, 0, 0], [0, length, 0], 0x15d84d],
    [[0, 0, 0], [0, 0, length], 0x265dff],
  ]
  for (const [from, to, color] of axes) {
    const start = helperPoint(from, zOffset)
    const end = helperPoint(to, zOffset)
    const axis =
      mode === 'mesh'
        ? createAxisMesh(start, end, color, radius)
        : createAxisLine(start, end, color, width)
    axis.renderOrder = renderOrder
    configureHelperMaterials(axis)
    targetScene.add(axis)
  }
}

function addGizmoLabels() {
  for (const label of GIZMO_LABELS) {
    const sprite = createGizmoLabel(label.axis, label.color)
    sprite.position.set(label.position[0], label.position[1], label.position[2])
    gizmoScene.add(sprite)
  }
}

function createGizmoLabel(text, color) {
  const size = 64
  const labelCanvas = document.createElement('canvas')
  labelCanvas.width = size
  labelCanvas.height = size
  const context = labelCanvas.getContext('2d')
  context.font = '700 34px Inter, Arial, sans-serif'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.lineWidth = 5
  context.strokeStyle = 'rgba(0, 0, 0, 0.72)'
  context.fillStyle = color
  context.strokeText(text, size / 2, size / 2)
  context.fillText(text, size / 2, size / 2)
  const texture = new THREE.CanvasTexture(labelCanvas)
  texture.needsUpdate = true
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(0.42, 0.42, 0.42)
  sprite.renderOrder = 20
  return sprite
}

function helperPoint(point, zOffset) {
  return new THREE.Vector3(point[0], point[1], point[2] + zOffset)
}

function createAxisLine(start, end, color, width) {
  const geometry = new THREE.BufferGeometry().setFromPoints([start, end])
  const material = new THREE.LineBasicMaterial({ color, linewidth: width, toneMapped: false })
  return new THREE.Line(geometry, material)
}

function createAxisMesh(start, end, color, radius) {
  const direction = new THREE.Vector3().subVectors(end, start)
  const length = direction.length()
  const geometry = new THREE.CylinderGeometry(radius, radius, length, 12, 1)
  const material = new THREE.MeshBasicMaterial({ color, toneMapped: false })
  const axis = new THREE.Mesh(geometry, material)
  axis.position.addVectors(start, end).multiplyScalar(0.5)
  axis.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize())
  return axis
}

function configureHelperMaterials(object) {
  const materials = Array.isArray(object.material) ? object.material : [object.material]
  for (const material of materials) {
    material.depthTest = true
    material.depthWrite = true
    material.toneMapped = false
  }
}

function createCloudLayers() {
  for (const source of CLOUD_SOURCES) {
    const geometry = new THREE.BufferGeometry()
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1000)
    const material = new THREE.PointsMaterial({
      size: pointSizeForSource(source),
      vertexColors: true,
      sizeAttenuation: false,
      map: pointSprite,
      alphaMap: pointSprite,
      transparent: true,
      opacity: opacityForSource(source),
      alphaTest: 0.36,
      depthWrite: false,
      depthTest: true,
      toneMapped: false,
    })
    const object = new THREE.Points(geometry, material)
    object.renderOrder = renderOrderForSource(source)
    object.visible = state.visibleSources.has(source)
    scene.add(object)
    state.layers[source] = {
      source,
      geometry,
      material,
      object,
      positions: new Float32Array(0),
      colors: new Float32Array(0),
      pointCount: 0,
      framePointCount: 0,
      sourcePointCount: 0,
      seq: 0,
      topic: '-',
      hz: 0,
      bounds: null,
      intensityRange: [0, 1],
      hasIntensity: false,
    }
  }
}

function renderOrderForSource(source) {
  if (source === 'map') return 0
  if (source === 'optimized') return 1
  return 2
}

function pointSizeForSource(source) {
  if (source === 'raw') return Math.max(0.7, state.pointSize * 1.08)
  if (source === 'map') return Math.max(0.5, state.pointSize * 0.72)
  return state.pointSize
}

function opacityForSource(source) {
  if (source === 'raw') return 0.96
  if (source === 'map') return 0.9
  return 0.95
}

function createPoseLayer() {
  poseGeometry = new THREE.BufferGeometry()
  const poseLine = new THREE.LineSegments(
    poseGeometry,
    new THREE.LineBasicMaterial({ vertexColors: true, toneMapped: false }),
  )
  poseMarker = new THREE.Mesh(
    new THREE.SphereGeometry(0.14, 16, 12),
    new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }),
  )
  poseMarker.visible = false
  scene.add(poseLine)
  scene.add(poseMarker)
}

function createGizmo() {
  const gizmoCanvas = document.createElement('canvas')
  gizmoCanvas.className = 'axis-gizmo'
  viewportPanel.appendChild(gizmoCanvas)
  gizmoRenderer = new THREE.WebGLRenderer({ canvas: gizmoCanvas, antialias: true, alpha: true })
  gizmoRenderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
  gizmoRenderer.setClearColor(0x000000, 0)
  gizmoScene = new THREE.Scene()
  gizmoCamera = new THREE.PerspectiveCamera(45, 1, 0.05, 20)
  gizmoCamera.up.set(0, 0, 1)
  addAxes(gizmoScene, GIZMO_AXES)
  addGizmoLabels()
}

function getSquarePointSprite() {
  const size = 64
  const spriteCanvas = document.createElement('canvas')
  spriteCanvas.width = size
  spriteCanvas.height = size
  const ctx = spriteCanvas.getContext('2d')
  ctx.clearRect(0, 0, size, size)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(spriteCanvas)
  texture.colorSpace = THREE.NoColorSpace
  texture.generateMipmaps = true
  texture.minFilter = THREE.LinearMipmapLinearFilter
  texture.magFilter = THREE.LinearFilter
  texture.needsUpdate = true
  return texture
}

function connect() {
  if (state.mockMode) {
    startMockStream()
    return
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${window.location.host}/ws`)
  ws.binaryType = 'arraybuffer'
  setConnectionState('connecting')

  ws.addEventListener('open', () => {
    setConnectionState('connected')
    requestAllSources()
    startHeartbeat()
  })
  ws.addEventListener('message', (event) => {
    if (typeof event.data === 'string') {
      handleJson(JSON.parse(event.data))
    } else {
      handleCloud(event.data)
    }
  })
  ws.addEventListener('close', () => {
    setConnectionState('disconnected')
    stopHeartbeat()
    scheduleReconnect()
  })
  ws.addEventListener('error', () => {
    setConnectionState('error')
  })
}

function requestAllSources() {
  if (state.mockMode || ws?.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ type: 'set_sources', sources: selectedLiveSources() }))
}

function selectedLiveSources() {
  return CLOUD_SOURCES.filter((source) => state.visibleSources.has(source))
}

function startMockStream() {
  setConnectionState('mock')
  setConnectionPill(connectionStateFromHealth('online'))
  updateMappingStatus(mockMappingSnapshot())
  const topicBySource = {
    raw: '/livox/lidar',
    optimized: '/web_mapping/current_frame',
    map: 'corrected_map',
  }
  let ticks = 0
  if (state.mockTimer) window.clearInterval(state.mockTimer)
  state.mockTimer = window.setInterval(() => {
    const elapsed = (performance.now() - state.mockStartTime) / 1000
    ticks += 1
    for (const source of SOURCES) {
      if (source === 'map' && ticks % 12 !== 1) continue
      const count = source === 'map' ? 36000 : source === 'raw' ? 12000 : 14000
      const values = buildMockCloud(count, elapsed, source)
      appendPoints(values, {
        seq: state.cloudSeq + 1,
        source,
        source_point_count: count,
        topic: topicBySource[source],
        has_intensity: true,
        intensity_range: [0, 1],
        bounds: {
          min: [-18, -16, -2],
          max: [18, 16, 7],
        },
      })
    }
    updatePose({
      type: 'pose',
      x: Math.cos(elapsed * 0.35) * 5.8,
      y: Math.sin(elapsed * 0.35) * 4.4,
      z: 1.1 + Math.sin(elapsed * 0.7) * 0.2,
      yaw: elapsed * 0.35 + Math.PI / 2,
    })
    updateImu({
      type: 'imu',
      topic: '/livox/imu',
      frame_id: 'livox_frame',
      angular_velocity: [
        Math.sin(elapsed * 0.8) * 0.05,
        Math.cos(elapsed * 0.6) * 0.05,
        0.18 + Math.sin(elapsed * 0.35) * 0.03,
      ],
      linear_acceleration: [
        Math.sin(elapsed * 0.9) * 0.12,
        Math.cos(elapsed * 0.7) * 0.12,
        9.81 + Math.sin(elapsed * 1.1) * 0.08,
      ],
      gyro_norm: 0.19,
      accel_norm: 9.81,
    })
    updatePath({
      type: 'path',
      source: 'optimized',
      points: buildMockPath(elapsed),
    })
    updateStatus({
      type: 'status',
      client_count: 1,
      lidar: {
        state: 'online',
        status_text: 'mock mapping stream',
        raw_topic: '/livox/lidar',
      },
      topics: {
        raw: mockTopic('raw', topicBySource.raw, 10),
        optimized: mockTopic('optimized', topicBySource.optimized, 10),
        map: mockTopic('map', topicBySource.map, 1),
        pose: mockTopic('pose', 'pose_stamped', 10),
        imu: mockTopic('imu', '/livox/imu', 100),
      },
      mapping: mockMappingSnapshot(),
    })
  }, 100)
}

function mockTopic(source, topic, hz) {
  const layer = state.layers[source]
  return {
    topic,
    hz,
    frames: state.cloudSeq,
    state: hz > 0 ? 'online' : 'waiting',
    last_points: layer?.sourcePointCount || 1,
    last_sampled_points: layer?.framePointCount || 1,
  }
}

function mockMappingSnapshot() {
  return {
    state: state.mapping.state,
    message: state.mapping.message,
    session_name: state.mapping.sessionName || '',
    save_directory: state.mapping.saveDirectory || '',
    last_command: state.mapping.lastCommand || '',
    backend: { name: 'mock', available: true },
    allowed_commands: allowedMappingCommands(state.mapping.state),
  }
}

function allowedMappingCommands(mappingState) {
  if (mappingState === 'stopped') return state.mapping.lidarValid ? ['save', 'start_lidar', 'stop_lidar', 'check_lidar', 'start'] : ['save', 'start_lidar', 'stop_lidar', 'check_lidar']
  if (mappingState === 'idle' || mappingState === 'error') return state.mapping.lidarValid ? ['start_lidar', 'stop_lidar', 'check_lidar', 'start'] : ['start_lidar', 'stop_lidar', 'check_lidar']
  if (mappingState === 'mapping') return ['stop']
  if (mappingState === 'starting') return ['stop']
  return []
}

function buildMockCloud(pointCount, elapsed, source) {
  const values = new Float32Array(pointCount * 4)
  for (let i = 0; i < pointCount; i += 1) {
    const t = i / Math.max(1, pointCount - 1)
    const ring = (i % 480) * (Math.PI / 240)
    const lane = Math.floor(i / 480) % 18
    const pass = Math.floor(i / (480 * 18))
    const corridor = (lane - 9) * 1.35
    const length = (t * 2 - 1) * 28
    const curve = Math.sin(length * 0.12 + pass * 0.4) * 4.5
    const sourceOffset = source === 'raw' ? Math.sin(elapsed * 1.5 + ring) * 0.45 : 0
    const idx = i * 4
    if (source === 'map') {
      values[idx] = length
      values[idx + 1] = corridor + Math.sin(length * 0.18) * 1.2
      values[idx + 2] = -0.8 + Math.sin(ring * 3 + pass) * 0.25 + (pass % 5) * 0.18
    } else {
      const radius = 2.8 + (lane / 18) * 10
      values[idx] = Math.cos(ring) * radius + Math.cos(elapsed * 0.35) * 5.8 + sourceOffset
      values[idx + 1] = Math.sin(ring) * radius + Math.sin(elapsed * 0.35) * 4.4
      values[idx + 2] = -1 + (lane / 18) * 6 + Math.sin(ring * 4 + elapsed) * 0.18
    }
    values[idx + 3] = (Math.sin(ring * 4 + elapsed + pass) + 1) * 0.5
  }
  return values
}

function buildMockPath(elapsed) {
  const points = []
  for (let i = 0; i < 240; i += 1) {
    const t = elapsed * 0.35 - (240 - i) * 0.012
    points.push([Math.cos(t) * 5.8, Math.sin(t) * 4.4, 1.1 + Math.sin(t * 2) * 0.2])
  }
  return points
}

function startHeartbeat() {
  stopHeartbeat()
  state.heartbeatTimer = window.setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping', time: Date.now() }))
    }
  }, 20000)
}

function stopHeartbeat() {
  if (!state.heartbeatTimer) return
  window.clearInterval(state.heartbeatTimer)
  state.heartbeatTimer = null
}

function scheduleReconnect() {
  if (state.reconnectTimer) return
  state.reconnectTimer = window.setTimeout(() => {
    state.reconnectTimer = null
    connect()
  }, 1200)
}

function setConnectionState(label) {
  state.bridgeConnected = label === 'connected' || label === 'mock'
  if (!state.bridgeConnected) {
    resetLiveStats()
    markBridgeOffline(label)
  }
  updateMappingControls()
}

function markBridgeOffline(label) {
  const offlineState = 'disconnected'
  const topics = offlineTopics(offlineState)
  setStatePill(ui.radarDetailState, offlineState)
  setStatePill(ui.imuState, offlineState)
  setStatePill(ui.poseState, offlineState)
  setConnectionPill('disconnected')
  setStatePill(ui.sensorHealthState, offlineState)
  ui.clientCount.textContent = '0'
  ui.radarHz.textContent = '0.00 Hz'
  ui.radarAge.textContent = '-'
  ui.radarTopic.textContent = '-'
  ui.radarPoints.textContent = '0'
  setStatePill(ui.webVizState, offlineState)
  ui.webVizHz.textContent = '0.00 Hz'
  ui.webVizAge.textContent = '-'
  ui.webVizPoints.textContent = '0'
  ui.webVizSourcePoints.textContent = '0'
  ui.poseHz.textContent = '0.00 Hz'
  ui.poseAge.textContent = '-'
  ui.imuHz.textContent = '0.00 Hz'
  ui.imuAge.textContent = '-'
  ui.sensorDataAge.textContent = '-'
  updatePipelineStatus(topics)
  updateBackendDetails(topics)
}

function offlineTopics(stateText) {
  return {
    raw: { state: stateText },
    optimized: { state: stateText },
    map: { state: stateText },
    pose: { state: stateText },
    imu: { state: stateText },
    optimized_path: { state: stateText },
  }
}

function handleJson(payload) {
  if (payload.type === 'status') updateStatus(payload)
  if (payload.type === 'mapping_status') updateMappingStatus(payload.mapping)
  if (payload.type === 'mapping_command_result') updateMappingCommandResult(payload)
  if (!state.bridgeConnected) return
  if (payload.type === 'pose' && !state.mapHistory.savedPreviewActive) {
    recordLiveStat('pose', payload)
    updatePose(payload)
  }
  if (payload.type === 'imu') {
    recordLiveStat('imu', payload)
    updateImu(payload)
  }
  if (payload.type === 'path' && !state.mapHistory.savedPreviewActive) updatePath(payload)
  if (payload.type === 'hello') requestAllSources()
}

function handleCloud(buffer) {
  if (!state.bridgeConnected) return
  appendCloudPayload(buffer)
}

function appendCloudPayload(buffer) {
  const { header, values } = decodeCloudPayload(buffer)
  if (!CLOUD_SOURCES.includes(header.source)) return
  if (state.mapHistory.savedPreviewActive && SAVED_MAP_SOURCES.includes(header.source)) return
  recordLiveStat(header.source, header)
  appendPoints(values, header)
}

function appendCloudPayloadAsSource(buffer, source) {
  const { header, values } = decodeCloudPayload(buffer)
  if (!CLOUD_SOURCES.includes(source)) return
  appendPoints(values, { ...header, source })
}

function decodeCloudPayload(buffer) {
  const view = new DataView(buffer)
  const headerLength = view.getUint32(0, true)
  const dataOffset = view.getUint32(4, true)
  const headerText = new TextDecoder().decode(buffer.slice(8, 8 + headerLength))
  const header = JSON.parse(headerText)
  const values = new Float32Array(buffer, dataOffset)
  return { header, values }
}

function appendPoints(values, header) {
  const source = header.source
  const layer = state.layers[source]
  if (!layer) return
  const incomingPoints = Math.floor(values.length / 4)
  const maxPoints = sourceBudget(source)
  const unlimited = !Number.isFinite(maxPoints)
  const shouldAccumulate = ACCUMULATING_SOURCES.has(source)
  const existingPoints = shouldAccumulate ? layer.pointCount : 0
  const combinedPoints = existingPoints + incomingPoints
  const nextPoints = unlimited ? combinedPoints : Math.min(maxPoints, combinedPoints)
  const nextPositions = new Float32Array(nextPoints * 3)
  const nextColors = new Float32Array(nextPoints * 3)

  const existingKeep = shouldAccumulate ? Math.min(existingPoints, Math.max(0, nextPoints - incomingPoints)) : 0
  if (existingKeep > 0) {
    const existingStart = existingPoints - existingKeep
    nextPositions.set(layer.positions.subarray(existingStart * 3, existingPoints * 3), 0)
    nextColors.set(layer.colors.subarray(existingStart * 3, existingPoints * 3), 0)
  }

  const incomingCapacity = nextPoints - existingKeep
  const incomingStart = Math.max(0, incomingPoints - incomingCapacity)
  const incomingKeep = incomingPoints - incomingStart
  const range = header.intensity_range || layer.intensityRange || [0, 1]
  const hasIntensity = Boolean(header.has_intensity)
  for (let i = 0; i < incomingKeep; i += 1) {
    const sourceIndex = (incomingStart + i) * 4
    const targetIndex = (existingKeep + i) * 3
    nextPositions[targetIndex] = values[sourceIndex]
    nextPositions[targetIndex + 1] = values[sourceIndex + 1]
    nextPositions[targetIndex + 2] = values[sourceIndex + 2]
    writePointColor(nextColors, targetIndex, source, hasIntensity ? values[sourceIndex + 3] : null, range)
  }

  layer.positions = nextPositions
  layer.colors = nextColors
  layer.pointCount = nextPoints
  layer.framePointCount = incomingPoints
  layer.sourcePointCount = shouldAccumulate
    ? (layer.sourcePointCount || 0) + (header.source_point_count || incomingPoints)
    : (header.source_point_count || incomingPoints)
  layer.seq = header.seq || layer.seq + 1
  layer.topic = header.topic || '-'
  layer.bounds = header.bounds || layer.bounds
  layer.intensityRange = range
  layer.hasIntensity = hasIntensity
  state.cloudSeq = Math.max(state.cloudSeq, layer.seq)
  state.latestFramePoints = incomingPoints
  state.bounds = recomputeBounds()
  uploadLayer(layer)
  if (layer.pointCount > 0 && layer.bounds) {
    recenterCamera(layer.bounds, source)
  }
  updatePointUi()
  updateMappingControls()
  updateMappingMessage()
}

function sourceBudget(source) {
  if (state.pointBudget >= UNLIMITED_POINT_BUDGET) return Number.POSITIVE_INFINITY
  if (source === 'optimized') return Math.max(100000, Math.floor(state.pointBudget * 0.75))
  if (source === 'map') return Math.max(100000, Math.floor(state.pointBudget * 0.75))
  return Math.max(10000, Math.floor(state.pointBudget * 0.1))
}

function writePointColor(colors, offset, source, intensity, range) {
  const t = intensityTone(intensity, range)
  if (source === 'optimized') {
    writeGradientColor(colors, offset, SCENE.optimizedLow, SCENE.optimizedHigh, t)
    return
  }
  if (source === 'raw') {
    writeRawScanColor(colors, offset, t)
    return
  }
  writeGradientColor(colors, offset, SCENE.mapLow, SCENE.mapHigh, t)
}

function intensityTone(intensity, range) {
  if (intensity === null) return 0.72
  const normalized = clamp((intensity - range[0]) / Math.max(0.0001, range[1] - range[0]), 0, 1)
  return Math.pow(normalized, 0.55)
}

function writeGradientColor(colors, offset, low, high, t) {
  colors[offset] = low.r + (high.r - low.r) * t
  colors[offset + 1] = low.g + (high.g - low.g) * t
  colors[offset + 2] = low.b + (high.b - low.b) * t
}

function writeRawScanColor(colors, offset, t) {
  for (let i = 1; i < RAW_COLOR_STOPS.length; i += 1) {
    if (t > RAW_COLOR_STOPS[i][0]) continue
    const [leftAt, leftColor] = RAW_COLOR_STOPS[i - 1]
    const [rightAt, rightColor] = RAW_COLOR_STOPS[i]
    const localT = clamp((t - leftAt) / Math.max(0.0001, rightAt - leftAt), 0, 1)
    writeGradientColor(colors, offset, leftColor, rightColor, localT)
    return
  }
  const lastColor = RAW_COLOR_STOPS[RAW_COLOR_STOPS.length - 1][1]
  writeGradientColor(colors, offset, lastColor, lastColor, 1)
}

function uploadLayer(layer) {
  layer.geometry.setAttribute('position', new THREE.BufferAttribute(layer.positions, 3))
  layer.geometry.setAttribute('color', new THREE.BufferAttribute(layer.colors, 3))
  layer.geometry.setDrawRange(0, layer.pointCount)
  layer.geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1000)
  layer.material.size = pointSizeForSource(layer.source)
  layer.material.opacity = opacityForSource(layer.source)
  layer.material.vertexColors = true
  layer.material.needsUpdate = true
}

function updateStatus(payload) {
  const topics = payload.topics || {}
  refreshLiveStats(topics)
  state.topicStats = topics
  const lidarState = payload.lidar?.state || 'disconnected'
  state.mapping.lidarState = lidarState
  state.mapping.lidarValid = Boolean(payload.lidar?.valid || topics.raw?.valid)
  state.mapping.lidarChecking = Boolean(payload.lidar?.checking)
  state.mapping.lidarMessage = payload.lidar?.message || payload.lidar?.status_text || state.mapping.lidarMessage
  const rawTopic = topics.raw || {}
  const imuTopic = topics.imu || {}
  const poseTopic = topics.pose || {}
  const lidar = payload.lidar || {}
  const lidarCheck = lidar.check || {}
  const sensorRawHz = Number.isFinite(lidar.hz) ? lidar.hz : lidarCheck.raw_hz
  const sensorRawAge = Number.isFinite(lidar.age_sec) ? lidar.age_sec : lidarCheck.raw_age_sec
  const sensorRawPoints = Number.isFinite(lidar.last_points) ? lidar.last_points : lidarCheck.raw_last_points
  const sensorImuHz = Number.isFinite(lidar.imu_hz) ? lidar.imu_hz : lidarCheck.imu_hz
  const sensorImuAge = Number.isFinite(lidar.imu_age_sec) ? lidar.imu_age_sec : lidarCheck.imu_age_sec
  const webRawPoints = rawTopic.last_sampled_points || rawTopic.last_points || 0
  const webRawSourcePoints = rawTopic.last_points || 0
  const healthState = sensorHealth(topics, lidarState)
  setStatePill(ui.radarDetailState, lidarState)
  setStatePill(ui.imuState, imuTopic.state || 'waiting')
  setStatePill(ui.poseState, poseTopic.state || 'waiting')
  setConnectionPill(connectionStateFromHealth(healthState))
  setStatePill(ui.sensorHealthState, healthState)
  ui.clientCount.textContent = String(payload.client_count ?? 0)
  ui.radarHz.textContent = `${formatHz(sensorRawHz)} Hz`
  ui.radarAge.textContent = formatAge(sensorRawAge)
  ui.radarTopic.textContent = rawTopic.topic || lidar.raw_topic || '-'
  ui.radarPoints.textContent = compact(sensorRawPoints || 0)
  ui.radarPoints.title = `传感器原始帧 ${compact(sensorRawPoints || 0)} 点`
  setStatePill(ui.webVizState, rawTopic.state || 'waiting')
  ui.webVizHz.textContent = `${formatHz(rawTopic.hz)} Hz`
  ui.webVizAge.textContent = formatStatAge(rawTopic, 'raw')
  ui.webVizPoints.textContent = compact(webRawPoints)
  ui.webVizSourcePoints.textContent = compact(webRawSourcePoints)
  ui.poseHz.textContent = `${formatHz(poseTopic.hz)} Hz`
  ui.poseAge.textContent = formatStatAge(poseTopic, 'pose')
  ui.imuHz.textContent = `${formatHz(Number.isFinite(sensorImuHz) ? sensorImuHz : imuTopic.hz)} Hz`
  ui.imuAge.textContent = formatAge(sensorImuAge)
  ui.sensorDataAge.textContent = latestDataAge([
    [rawTopic, 'raw'],
    [imuTopic, 'imu'],
    [poseTopic, 'pose'],
  ])
  for (const source of SOURCES) {
    if (state.layers[source]) state.layers[source].hz = topics[source]?.hz || 0
  }
  updatePipelineStatus(topics)
  updateBackendDetails(topics)
  if (payload.mapping) updateMappingStatus(payload.mapping)
  if (payload.pose) updatePose(payload.pose)
  if (payload.imu) updateImu(payload.imu)
  updatePointUi()
  updateMappingMessage()
}

function updateMappingCommandResult(payload) {
  if (payload.mapping) updateMappingStatus(payload.mapping)
  if (payload.command && payload.command === state.mapping.pendingCommand) {
    state.mapping.pendingCommand = ''
    state.mapping.pendingSince = 0
  }
  if (!payload.accepted) {
    if (payload.command === 'stop') {
      state.mapHistory.pendingStopRefresh = false
      state.mapHistory.stopPreviousLatest = null
      state.mapHistory.stopStartedAt = 0
    }
    updateMappingMessage(payload.message || '建图指令执行失败')
    return
  }
  if (payload.command === 'stop') {
    state.mapHistory.pendingStopRefresh = true
    updateMappingMessage('正在停止并保存地图')
    return
  }
  if (payload.command === 'start') {
    resetLiveMappingScene()
  }
  updateMappingMessage()
}

function updateMappingStatus(mapping) {
  if (!mapping) return
  if (shouldHoldPendingMappingState(mapping)) {
    updateMappingControls()
    updateMappingMessage()
    return
  }
  const previousMappingState = state.mapping.state
  state.mapping = {
    ...state.mapping,
    state: mapping.state || state.mapping.state,
    message: mapping.message || state.mapping.message,
    allowedCommands: mapping.allowed_commands || state.mapping.allowedCommands,
    sessionName: mapping.session_name || '',
    saveDirectory: mapping.save_directory || '',
    lidarState: mapping.lidar_state || state.mapping.lidarState,
    lidarValid: Boolean(mapping.lidar_valid ?? state.mapping.lidarValid),
    lidarChecking: Boolean(mapping.lidar_checking ?? state.mapping.lidarChecking),
    lidarMessage: mapping.lidar_message || state.mapping.lidarMessage,
    lastCommand: mapping.last_command || '',
    postprocess: mapping.postprocess || state.mapping.postprocess || {},
  }
  if (pendingMappingCommandIsSettled(state.mapping.pendingCommand, state.mapping.state)) {
    state.mapping.pendingCommand = ''
    state.mapping.pendingSince = 0
  }
  setMappingStatePill(state.mapping.state)
  updateMappingControls()
  updateMappingMessage()
  if (
    state.mapHistory.pendingStopRefresh &&
    previousMappingState !== 'stopped' &&
    state.mapping.state === 'stopped'
  ) {
    handleStopCompleted()
  }
}

function shouldHoldPendingMappingState(mapping) {
  if (!state.mapping.pendingCommand) return false
  if (mappingCommandTimedOut()) return false
  const incomingState = mapping.state || ''
  if (pendingMappingCommandIsSettled(state.mapping.pendingCommand, incomingState)) return false
  if (state.mapping.pendingCommand === 'start') {
    return ['idle', 'stopped', 'mapping'].includes(incomingState)
  }
  if (state.mapping.pendingCommand === 'stop') {
    return ['starting', 'mapping'].includes(incomingState)
  }
  if (state.mapping.pendingCommand === 'start_lidar' || state.mapping.pendingCommand === 'stop_lidar' || state.mapping.pendingCommand === 'check_lidar') {
    return false
  }
  return false
}

function pendingMappingCommandIsSettled(command, mappingState) {
  if (command === 'start') return ['starting', 'mapping', 'error'].includes(mappingState)
  if (command === 'stop') return ['stopping', 'stopped', 'error', 'idle'].includes(mappingState)
  if (command === 'start_lidar') return !['starting'].includes(state.mapping.lidarState)
  if (command === 'stop_lidar') return !['stopping'].includes(state.mapping.lidarState)
  if (command === 'check_lidar') return !state.mapping.lidarChecking && state.mapping.lidarState !== 'checking'
  return true
}

function setMappingStatePill(stateText) {
  const next = stateText || 'idle'
  ui.mappingState.textContent = MAPPING_STATE_LABELS[next] || next
  ui.mappingState.classList.remove('is-online', 'is-stale', 'is-waiting', 'is-disconnected')
  ui.mappingState.classList.add(MAPPING_STATE_CLASS[next] || 'is-waiting')
}

function updateMappingControls() {
  const allowed = new Set(state.mapping.allowedCommands || [])
  const canSend = state.bridgeConnected || state.mockMode
  const lidarBusy = state.mapping.lidarChecking || state.mapping.lidarState === 'checking' || state.mapping.lidarState === 'starting' || state.mapping.lidarState === 'stopping'
  const commandBusy = pendingCommandActive()
  const lidarCommandBusy = commandBusy && LIDAR_COMMANDS.has(state.mapping.pendingCommand)
  const mappingCommandBusy = commandBusy && MAPPING_COMMANDS.has(state.mapping.pendingCommand)
  ui.startLidar.disabled = !canSend || lidarBusy || lidarCommandBusy || !allowed.has('start_lidar')
  ui.stopLidar.disabled = !canSend || lidarBusy || lidarCommandBusy || !allowed.has('stop_lidar')
  ui.checkLidar.disabled = !canSend || lidarBusy || lidarCommandBusy || !allowed.has('check_lidar')
  ui.startMapping.disabled = !canSend || lidarBusy || mappingCommandBusy || !allowed.has('start') || !state.mapping.lidarValid
  ui.stopMapping.disabled = !canSend || mappingCommandBusy || !allowed.has('stop')
  ui.mappingSessionName.disabled = !canSend || lidarBusy || mappingCommandBusy || !allowed.has('start') || !state.mapping.lidarValid
}

function pendingCommandActive() {
  if (!state.mapping.pendingCommand) return false
  if (mappingCommandTimedOut()) {
    state.mapping.pendingCommand = ''
    state.mapping.pendingSince = 0
    return false
  }
  return true
}

function mappingCommandTimedOut() {
  return Boolean(state.mapping.pendingCommand && performance.now() - state.mapping.pendingSince > COMMAND_PENDING_TIMEOUT_MS)
}

function canSendMappingCommand(command) {
  if (!state.mockMode && ws?.readyState !== WebSocket.OPEN) return false
  if (pendingCommandActive()) return false
  const allowed = new Set(state.mapping.allowedCommands || [])
  const lidarBusy = state.mapping.lidarChecking || state.mapping.lidarState === 'checking' || state.mapping.lidarState === 'starting' || state.mapping.lidarState === 'stopping'
  if (LIDAR_COMMANDS.has(command)) return !lidarBusy && allowed.has(command)
  if (command === 'start') return !lidarBusy && state.mapping.lidarValid && allowed.has(command)
  if (command === 'stop') return allowed.has(command)
  return allowed.has(command)
}

function hasSavableMapPoints() {
  return (state.layers.map?.pointCount || 0) > 0 || (state.layers.optimized?.pointCount || 0) > 0
}

function hasRawScanPoints() {
  const rawLayer = state.layers.raw
  const rawStat = state.topicStats.raw || {}
  return (rawLayer?.pointCount || 0) > 0 || (rawStat.last_points || 0) > 0
}

function hasMappingOutputPoints() {
  const optimizedStat = state.topicStats.optimized || {}
  const mapStat = state.topicStats.map || {}
  return hasSavableMapPoints() || (optimizedStat.last_points || 0) > 0 || (mapStat.last_points || 0) > 0
}

function updateMappingMessage(overrideText = '') {
  if (overrideText) {
    ui.mappingMessage.textContent = overrideText
    return
  }
  setMappingStatePill(state.mapping.state)
  ui.mappingMessage.textContent = mappingProgressMessage()
}

function mappingProgressMessage() {
  const mappingState = state.mapping.state
  if (mappingState === 'idle') return '等待开始'
  if (mappingState === 'starting') return '正在初始化，请稍等'
  if (mappingState === 'mapping') {
    if (hasMappingOutputPoints()) return '正在建图，地图持续更新中'
    if (hasRawScanPoints()) return '已收到雷达数据，正在生成地图'
    return '正在建图，地图持续更新中'
  }
  if (mappingState === 'saving') return state.mapping.message || '正在保存地图'
  if (mappingState === 'stopping') return state.mapping.message || '正在停止并保存地图'
  if (mappingState === 'stopped') {
    if (state.mapping.message) return state.mapping.message
    if (hasSavableMapPoints()) return '建图已停止'
    if (hasRawScanPoints()) return '建图已停止，但还没有可保存的地图'
    return '建图已停止'
  }
  if (mappingState === 'error') return state.mapping.message || '建图未启动，请检查雷达和定位数据'
  return state.mapping.message || '-'
}

function sendMappingCommand(command) {
  if (!canSendMappingCommand(command)) return
  if (command === 'start_lidar' || command === 'stop_lidar' || command === 'check_lidar') {
    state.mapping.pendingCommand = command
    state.mapping.pendingSince = performance.now()
    state.mapping.message = command === 'start_lidar' ? '正在启动雷达' : command === 'stop_lidar' ? '正在关闭雷达' : '正在检测雷达'
    if (command === 'start_lidar') {
      state.mapping.lidarState = 'starting'
      state.mapping.lidarValid = false
      state.mapping.lidarChecking = false
    } else if (command === 'stop_lidar') {
      state.mapping.lidarState = 'stopping'
      state.mapping.lidarValid = false
      state.mapping.lidarChecking = false
    } else {
      state.mapping.lidarState = 'checking'
      state.mapping.lidarValid = false
      state.mapping.lidarChecking = true
    }
    updateMappingControls()
    updateMappingMessage(state.mapping.message)
  }
  if (command === 'start') {
    state.mapping.state = 'starting'
    state.mapping.message = '正在初始化，请稍等'
    state.mapping.allowedCommands = []
    state.mapping.pendingCommand = 'start'
    state.mapping.pendingSince = performance.now()
    updateMappingControls()
    updateMappingMessage('正在初始化，请稍等')
  }
  if (command === 'stop') {
    state.mapHistory.stopPreviousLatest = state.mapHistory.sessions?.[0] || null
    state.mapHistory.stopStartedAt = Date.now() / 1000
    state.mapHistory.pendingStopRefresh = true
    state.mapping.state = 'stopping'
    state.mapping.message = '正在停止并保存地图'
    state.mapping.allowedCommands = []
    state.mapping.pendingCommand = 'stop'
    state.mapping.pendingSince = performance.now()
    updateMappingControls()
    updateMappingMessage('正在停止并保存地图')
  }
  const payload = {
    type: 'mapping_command',
    command,
    session_name: ui.mappingSessionName.value.trim(),
    save_directory: '',
  }
  if (state.mockMode) {
    applyMockMappingCommand(payload)
    return
  }
  ws.send(JSON.stringify(payload))
}

function applyMockMappingCommand(payload) {
  const command = payload.command
  const current = state.mapping.state
  const allowed = new Set(allowedMappingCommands(current))
  if (!allowed.has(command)) {
    updateMappingCommandResult({
      command,
      accepted: false,
      message: `${MAPPING_STATE_LABELS[current] || current} 状态下不能执行此操作`,
      mapping: mockMappingSnapshot(),
    })
    return
  }
  if (command === 'start') {
    state.mapping.state = 'mapping'
    state.mapping.message = '正在初始化，请稍等'
    state.mapping.sessionName = payload.session_name
    state.mapping.saveDirectory = payload.save_directory
  } else if (command === 'start_lidar') {
    state.mapping.lidarState = 'waiting'
    state.mapping.lidarValid = false
    state.mapping.message = '已请求启动雷达，请检测数据'
  } else if (command === 'stop_lidar') {
    state.mapping.lidarState = 'disconnected'
    state.mapping.lidarValid = false
    state.mapping.message = '雷达已关闭'
  } else if (command === 'check_lidar') {
    state.mapping.lidarState = 'online'
    state.mapping.lidarValid = true
    state.mapping.message = '雷达数据有效'
  } else if (command === 'stop') {
    state.mapping.state = 'stopping'
    state.mapping.message = '正在停止并保存地图'
  }
  state.mapping.lastCommand = command
  updateMappingCommandResult({
    command,
    accepted: true,
    message: state.mapping.message,
    mapping: mockMappingSnapshot(),
  })
}

async function loadMapHistory() {
  if (!ui.historyList || state.mapHistory.loading) return
  state.mapHistory.loading = true
  setMapHistoryRefreshState(true)
  renderMapHistory({ loading: true, sessions: state.mapHistory.sessions })
  try {
    const response = await fetch('/api/maps', { cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.json()
    state.mapHistory.sessions = payload.sessions || []
    renderMapHistory(payload)
  } catch (error) {
    renderMapHistory({
      available: false,
      sessions: state.mapHistory.sessions,
      message: '读取失败，请稍后重试',
    })
  } finally {
    state.mapHistory.loading = false
    setMapHistoryRefreshState(false)
  }
}

function setMapHistoryRefreshState(loading) {
  ui.refreshHistory.disabled = loading
  ui.refreshHistory.classList.toggle('is-loading', loading)
  ui.refreshHistory.setAttribute('aria-busy', String(loading))
}

async function handleStopCompleted() {
  const previousLatest = state.mapHistory.stopPreviousLatest || state.mapHistory.sessions?.[0]
  const startedAt = state.mapHistory.stopStartedAt
  state.mapHistory.stopPreviousLatest = null
  state.mapHistory.stopStartedAt = 0
  state.mapHistory.pendingStopRefresh = false
  updateMappingMessage('地图保存完成，正在刷新地图库')
  const latest = await waitForSavedMap(previousLatest, startedAt)
  if (latest?.archive_url) {
    updateMappingMessage('地图已保存，地图库已刷新')
    return
  }
  await loadMapHistory()
  updateMappingMessage('建图已停止，未发现新的地图文件')
}

async function waitForSavedMap(previousLatest, minModifiedAt = 0) {
  const previousId = previousLatest?.id || ''
  const previousVersion = mapSessionVersion(previousLatest)
  for (let attempt = 0; attempt < SAVE_DOWNLOAD_ATTEMPTS; attempt += 1) {
    await loadMapHistory()
    const latest = state.mapHistory.sessions?.[0]
    if (isNewSavedMap(latest, previousId, previousVersion, minModifiedAt)) return latest
    await sleep(SAVE_DOWNLOAD_INTERVAL_MS)
  }
  return null
}

function isNewSavedMap(session, previousId, previousVersion, minModifiedAt) {
  if (!session?.archive_url) return false
  const version = mapSessionVersion(session)
  const updatedAfterCommand = !minModifiedAt || version >= minModifiedAt - 2
  if (!updatedAfterCommand) return false
  if (!previousId) return true
  if (session.id !== previousId) return true
  return version > previousVersion
}

function downloadMapArchive(session) {
  if (!session?.archive_url) return
  window.location.assign(session.archive_url)
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function mapSessionVersion(session) {
  return Number(session?.modified_at || 0)
}

function renderMapHistory(payload) {
  const sessions = payload.sessions || state.mapHistory.sessions || []
  if (payload.loading) {
    const hasExistingList = ui.historyList.querySelector('.history-item')
    ui.historySummary.textContent = sessions.length > 0 ? `${sessions.length} 份地图，正在刷新` : '正在读取'
    if (!hasExistingList) {
      ui.historyList.innerHTML = '<p class="history-empty">正在读取地图库</p>'
    }
    return
  }
  if (sessions.length === 0) {
    ui.historySummary.textContent = ''
    ui.historyList.innerHTML = '<p class="history-empty">暂无可下载地图</p>'
    syncHistoryToolbar()
    return
  }
  if (state.mapHistory.selectedSessionId && !findMapSession(state.mapHistory.selectedSessionId)) {
    state.mapHistory.selectedSessionId = ''
  }
  ui.historySummary.textContent = `${sessions.length} 份地图`
  ui.historyList.innerHTML = sessions.map((session) => historySessionHtml(session)).join('')
  syncHistoryToolbar()
}

function historySessionHtml(session) {
  const files = session.files || []
  const sessionId = session.id || session.name
  const deleting = state.mapHistory.deleting === sessionId
  const postprocessing = state.mapHistory.postprocessing === sessionId
  const rendered = renderedMapSessionId() === sessionId
  const progress = mapSessionRenderProgress(sessionId)
  const selected = state.mapHistory.selectedSessionId === sessionId
  return `
    <details class="history-item${rendered ? ' is-rendered' : ''}${progress ? ' is-rendering' : ''}${selected ? ' is-selected' : ''}${deleting || postprocessing ? ' is-busy' : ''}" data-session-id="${escapeAttr(sessionId)}">
      <summary class="history-item-head">
        <span class="history-expand-icon" aria-hidden="true"></span>
        <span class="history-item-text">
          <strong title="${escapeAttr(session.path || session.name)}">
            <span class="history-render-led" title="当前画布正在显示" aria-hidden="true"></span>
            <span>${escapeHtml(session.name)}</span>
          </strong>
          <em>${escapeHtml(session.modified_label || '')}</em>
        </span>
        <span class="history-select-led" title="${selected ? '已选中' : '未选中'}" aria-hidden="true"></span>
        ${progress ? historyProgressHtml(progress) : ''}
      </summary>
      <div class="history-files">
        ${historyPostprocessHtml(session)}
        ${files.map((file) => historyFileHtml(file, sessionId)).join('')}
      </div>
    </details>
  `
}

function historyPostprocessHtml(session) {
  const postprocess = session.postprocess || {}
  const stateText = postprocess.state || ''
  const algorithm = postprocess.algorithm || 'clean_map_v1'
  const inputPoints = Number(postprocess.input_points || 0)
  const outputPoints = Number(postprocess.output_points || 0)
  const retention = Number(postprocess.retention_ratio || 0)
  const duration = Number(postprocess.duration_sec || 0)
  const config = postprocess.config || {}
  const preset = postprocess.preset || config.preset || ''
  if (!stateText && !inputPoints && !outputPoints) {
    return '<div class="history-postprocess-summary is-empty">后处理诊断：暂无</div>'
  }
  const statusLabel = stateText === 'completed' ? '完成' : stateText === 'failed' ? '失败' : stateText
  const ratioText = inputPoints > 0 ? `${(retention * 100).toFixed(1)}%` : '-'
  const configText = [
    Number.isFinite(Number(config.voxel_size)) ? `voxel ${formatNumber(config.voxel_size, 2)}` : '',
    Number.isFinite(Number(config.radius)) ? `radius ${formatNumber(config.radius, 2)}` : '',
    Number.isFinite(Number(config.min_neighbors)) ? `neighbors ${config.min_neighbors}` : '',
  ].filter(Boolean).join(' / ')
  return `
    <div class="history-postprocess-summary is-${escapeAttr(stateText || 'unknown')}">
      <span><strong>后处理诊断</strong><em>${escapeHtml(algorithm)} · ${escapeHtml(postprocessPresetLabel(preset) || statusLabel || '-')}</em></span>
      <span><strong>${compact(inputPoints)} → ${compact(outputPoints)}</strong><em>保留率 ${ratioText}</em></span>
      <span><strong>${formatSeconds(duration)}</strong><em>${escapeHtml(configText || '-')}</em></span>
    </div>
  `
}

function postprocessPresetForSession(sessionId, session) {
  const selected = state.mapHistory.postprocessPresets?.[sessionId]
  if (selected && selected !== currentPostprocessPreset(session)) return selected
  return selectablePostprocessPreset(session)
}

function currentPostprocessPreset(session) {
  const preset = session?.postprocess?.preset || session?.postprocess?.config?.preset || 'default'
  return POSTPROCESS_PRESETS.some((item) => item.id === preset) ? preset : 'default'
}

function selectablePostprocessPreset(session) {
  const current = currentPostprocessPreset(session)
  return POSTPROCESS_PRESETS.find((item) => item.id !== current)?.id || 'default'
}

function postprocessPresetLabel(presetId) {
  return POSTPROCESS_PRESETS.find((item) => item.id === presetId)?.label || ''
}

function mapSessionRenderProgress(sessionId) {
  const progress = state.mapHistory.renderProgress
  if (!progress.visible || progress.sessionId !== sessionId) return null
  return progress
}

function historyProgressHtml(progress) {
  const value = progress ? clamp(Number(progress.value || 0), 0, 100) : 0
  const status = progress?.status || 'idle'
  return `
    <div class="history-inline-progress is-${escapeAttr(status)}" aria-hidden="${progress ? 'false' : 'true'}">
      <span style="width: ${value}%"></span>
    </div>
  `
}

function mapPreviewFiles(files) {
  return [
    backendPreviewFile(files),
    frontendPreviewFile(files),
  ].filter(Boolean)
}

function backendPreviewFile(files) {
  const globalMap = files.find((file) => file.kind === 'global_optimized_map' && file.preview_url)
    || files.find((file) => isGlobalOptimizedMapFile(file.name) && file.preview_url)
  if (globalMap) return globalMap
  const hasAccumulated = files.some((file) => file.kind === 'accumulated_map' || isAccumulatedMapFile(file.name))
    || files.some((file) => file.kind === 'frontend_map' || isFrontendMapFile(file.name))
  if (hasAccumulated) return null
  return files.find((file) => file.kind === 'backend_map' && file.preview_url)
    || files.find((file) => isLegacyBackendMapFile(file.name) && file.preview_url)
}

function frontendPreviewFile(files) {
  return files.find((file) => file.kind === 'accumulated_map' && file.preview_url)
    || files.find((file) => isAccumulatedMapFile(file.name) && file.preview_url)
    || files.find((file) => file.kind === 'frontend_map' && file.preview_url)
    || files.find((file) => isFrontendMapFile(file.name) && file.preview_url)
}

function historyFileHtml(file, sessionId) {
  const label = mapFileLabel(file.name)
  return `
    <button class="history-file-row" type="button" data-session-id="${escapeAttr(sessionId)}">
      <span class="history-download-text">
        <strong>${escapeHtml(label)}</strong>
        <em>${formatBytes(file.size)}</em>
      </span>
    </button>
  `
}

function selectMapSession(sessionId) {
  if (!sessionId || !findMapSession(sessionId)) return
  state.mapHistory.selectedSessionId = sessionId
  updateHistorySelectionState()
  syncHistoryToolbar()
}

function updateHistorySelectionState() {
  const selectedId = state.mapHistory.selectedSessionId
  for (const item of ui.historyList?.querySelectorAll('.history-item') || []) {
    const selected = item.dataset.sessionId === selectedId
    item.classList.toggle('is-selected', selected)
    const led = item.querySelector('.history-select-led')
    if (led) led.title = selected ? '已选中' : '未选中'
  }
}

function selectedMapSession() {
  return findMapSession(state.mapHistory.selectedSessionId)
}

function syncHistoryToolbar() {
  const session = selectedMapSession()
  const sessionId = session ? (session.id || session.name) : ''
  const files = session?.files || []
  const hasPreview = mapPreviewFiles(files).length > 0
  const canDownload = Boolean(session?.archive_url)
  const deleting = sessionId && state.mapHistory.deleting === sessionId
  const previewing = sessionId && state.mapHistory.previewing === sessionId
  const postprocessing = sessionId && state.mapHistory.postprocessing === sessionId
  const busy = Boolean(deleting || previewing || postprocessing)
  const canPostprocess = Boolean(frontendPreviewFile(files))
  if (ui.historyPreviewSelected) {
    ui.historyPreviewSelected.disabled = !session || !hasPreview || busy
  }
  if (ui.historyDownloadSelected) {
    ui.historyDownloadSelected.href = canDownload ? session.archive_url : '#'
    ui.historyDownloadSelected.dataset.sessionName = session?.name || ''
    ui.historyDownloadSelected.classList.toggle('is-disabled', !canDownload || busy)
    ui.historyDownloadSelected.setAttribute('aria-disabled', String(!canDownload || busy))
  }
  if (ui.historyDeleteSelected) {
    ui.historyDeleteSelected.disabled = !session || busy
  }
  if (ui.historyPostprocessPreset) {
    syncPostprocessPresetOptions(session)
    ui.historyPostprocessPreset.disabled = !session || !canPostprocess || busy
    ui.historyPostprocessPreset.value = session ? postprocessPresetForSession(sessionId, session) : 'default'
  }
  if (ui.historyPostprocessSelected) {
    ui.historyPostprocessSelected.disabled = !session || !canPostprocess || busy
  }
}

function syncPostprocessPresetOptions(session) {
  if (!ui.historyPostprocessPreset) return
  const current = session ? currentPostprocessPreset(session) : ''
  for (const option of ui.historyPostprocessPreset.options) {
    const isCurrent = Boolean(current && option.value === current)
    option.disabled = isCurrent
    option.textContent = isCurrent
      ? `${postprocessPresetLabel(option.value) || option.value}（当前）`
      : postprocessPresetLabel(option.value) || option.value
  }
}

async function previewMapSession(sessionId) {
  const session = findMapSession(sessionId)
  const files = mapPreviewFiles(session?.files || [])
  if (!session || files.length === 0 || state.mapHistory.previewing) return
  state.mapHistory.previewing = sessionId
  setHistoryRenderProgress({
    visible: true,
    value: 4,
    stage: '提交渲染任务',
    detail: `准备读取 ${files.length} 份点云`,
    status: 'running',
    fileName: session.name || sessionId,
    sessionId,
  })
  renderMapHistory({ sessions: state.mapHistory.sessions })
  updateMappingMessage('正在渲染保存地图')
  try {
    state.mapHistory.savedPreviewActive = true
    state.mapHistory.activePreviewId = sessionId
    renderMapHistory({ sessions: state.mapHistory.sessions })
    clearSavedMapLayers()
    clearTrajectory({ clearPose: true })
    state.visibleSources.add('map')
    state.visibleSources.add('optimized')
    syncLayerVisibility()
    syncLayerButtons()
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index]
      const source = isAccumulatedMapFile(file.name) || isFrontendMapFile(file.name)
        || file.kind === 'accumulated_map' || file.kind === 'frontend_map'
        ? 'optimized'
        : 'map'
      await fetchAndAppendPreviewFile(file, source, index, files.length)
    }
    setHistoryRenderProgress({ value: 96, stage: '调整视角', detail: '同步双图视角' })
    resetCameraView()
    const backendPoints = state.layers.map?.pointCount || 0
    const frontendPoints = state.layers.optimized?.pointCount || 0
    setHistoryRenderProgress({
      value: 100,
      stage: '渲染完成',
      detail: `后端 ${compact(backendPoints)} / 前端 ${compact(frontendPoints)} 点`,
      status: 'success',
    })
    updateMappingMessage('保存地图已渲染')
  } catch (error) {
    if (!hasSavedPreviewPoints()) {
      state.mapHistory.savedPreviewActive = false
      state.mapHistory.activePreviewId = ''
    }
    setHistoryRenderProgress({ value: 100, stage: '渲染失败', detail: '请稍后重试', status: 'error' })
    updateMappingMessage('渲染地图失败')
  } finally {
    state.mapHistory.previewing = ''
    renderMapHistory({ sessions: state.mapHistory.sessions })
    scheduleHistoryRenderProgressHide()
  }
}

function findMapSession(sessionId) {
  return state.mapHistory.sessions.find((session) => (session.id || session.name) === sessionId)
}

function renderedMapSessionId() {
  return state.mapHistory.savedPreviewActive ? state.mapHistory.activePreviewId : ''
}

function hasSavedPreviewPoints() {
  return SAVED_MAP_SOURCES.some((source) => (state.layers[source]?.pointCount || 0) > 0)
}

async function fetchAndAppendPreviewFile(file, source, index, total) {
  const label = mapFileLabel(file.name)
  const base = 8 + (index / total) * 78
  const span = 78 / total
  const url = new URL(file.preview_url, window.location.origin)
  const previewBudget = sourceBudget(source)
  url.searchParams.set('max_points', String(Number.isFinite(previewBudget) ? previewBudget : UNLIMITED_POINT_BUDGET))
  setHistoryRenderProgress({ value: base, stage: `请求${label}`, detail: `${index + 1} / ${total}` })
  const response = await fetch(url.toString(), { cache: 'no-store' })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const buffer = await readPreviewBuffer(response, {
    base: base + span * 0.1,
    span: span * 0.66,
    label,
  })
  setHistoryRenderProgress({ value: base + span * 0.8, stage: `解析${label}`, detail: formatBytes(buffer.byteLength) })
  await nextFrame()
  setHistoryRenderProgress({ value: base + span * 0.92, stage: `写入${label}`, detail: SOURCE_LABELS[source] || label })
  appendCloudPayloadAsSource(buffer, source)
  syncLayerVisibility()
}

async function readPreviewBuffer(response, progress = {}) {
  const total = Number(response.headers.get('Content-Length') || 0)
  const base = Number.isFinite(progress.base) ? progress.base : 18
  const span = Number.isFinite(progress.span) ? progress.span : 52
  const label = progress.label || '点云数据'
  if (!response.body?.getReader) {
    setHistoryRenderProgress({ value: base + span * 0.25, stage: `下载${label}`, detail: '读取中' })
    const buffer = await response.arrayBuffer()
    setHistoryRenderProgress({ value: base + span, stage: `下载${label}`, detail: formatBytes(buffer.byteLength) })
    return buffer
  }
  const reader = response.body.getReader()
  const chunks = []
  let loaded = 0
  let estimatedProgress = base
  setHistoryRenderProgress({ value: estimatedProgress, stage: `下载${label}`, detail: total > 0 ? `0 / ${formatBytes(total)}` : '读取中' })
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    loaded += value.byteLength
    if (total > 0) {
      const downloadProgress = base + (loaded / total) * span
      setHistoryRenderProgress({
        value: downloadProgress,
        stage: `下载${label}`,
        detail: `${formatBytes(loaded)} / ${formatBytes(total)}`,
      })
    } else {
      estimatedProgress = Math.min(base + span, estimatedProgress + Math.max(1.5, span * 0.35 / Math.max(1, chunks.length)))
      setHistoryRenderProgress({
        value: estimatedProgress,
        stage: `下载${label}`,
        detail: formatBytes(loaded),
      })
    }
    await nextFrame()
  }
  setHistoryRenderProgress({ value: base + span, stage: `下载${label}`, detail: formatBytes(loaded) })
  return concatUint8Chunks(chunks, loaded).buffer
}

function concatUint8Chunks(chunks, totalBytes) {
  const output = new Uint8Array(totalBytes)
  let offset = 0
  for (const chunk of chunks) {
    output.set(chunk, offset)
    offset += chunk.byteLength
  }
  return output
}

function setHistoryRenderProgress(patch) {
  const progress = state.mapHistory.renderProgress
  if (progress.hideTimer) {
    window.clearTimeout(progress.hideTimer)
    progress.hideTimer = null
  }
  Object.assign(progress, patch)
  progress.value = clamp(Number(progress.value || 0), 0, 100)
  renderHistoryRenderProgress()
}

function renderHistoryRenderProgress() {
  const progress = state.mapHistory.renderProgress
  if (!progress.sessionId) return
  const item = historyItemElement(progress.sessionId)
  if (!item) return
  item.classList.toggle('is-rendering', progress.visible)
  const head = item.querySelector('.history-item-head')
  if (!head) return
  let inlineProgress = head.querySelector('.history-inline-progress')
  if (!inlineProgress) {
    inlineProgress = document.createElement('div')
    inlineProgress.className = 'history-inline-progress'
    inlineProgress.innerHTML = '<span></span>'
    head.appendChild(inlineProgress)
  }
  inlineProgress.hidden = !progress.visible
  inlineProgress.setAttribute('aria-hidden', String(!progress.visible))
  inlineProgress.classList.remove('is-running', 'is-success', 'is-error', 'is-idle')
  inlineProgress.classList.add(`is-${progress.status || 'idle'}`)
  const fill = inlineProgress.querySelector('span')
  if (fill) fill.style.width = `${progress.value}%`
}

function scheduleHistoryRenderProgressHide() {
  const progress = state.mapHistory.renderProgress
  const sessionId = progress.sessionId
  if (progress.hideTimer) window.clearTimeout(progress.hideTimer)
  progress.hideTimer = window.setTimeout(() => {
    progress.visible = false
    progress.value = 0
    progress.stage = '等待任务'
    progress.detail = '-'
    progress.status = 'idle'
    progress.fileName = ''
    progress.sessionId = ''
    progress.hideTimer = null
    renderHistoryRenderProgress()
    if (sessionId) hideHistoryItemProgress(sessionId)
  }, progress.status === 'error' ? 3200 : 1800)
}

function historyItemElement(sessionId) {
  return Array.from(ui.historyList?.querySelectorAll('.history-item') || [])
    .find((item) => item.dataset.sessionId === sessionId)
}

function hideHistoryItemProgress(sessionId) {
  const item = historyItemElement(sessionId)
  item?.classList.remove('is-rendering')
  const inlineProgress = item?.querySelector('.history-item-head .history-inline-progress')
  if (!inlineProgress) return
  inlineProgress.hidden = true
  inlineProgress.setAttribute('aria-hidden', 'true')
  const fill = inlineProgress.querySelector('span')
  if (fill) fill.style.width = '0%'
}

function normalizeMapLibraryMessage(message) {
  const text = String(message || '').trim()
  if (!text || text.toLowerCase() === 'ok') return ''
  return text.replaceAll('历史地图', '地图库')
}

function nextFrame() {
  return new Promise((resolve) => window.requestAnimationFrame(() => resolve()))
}

async function deleteMapSession(sessionId, sessionName) {
  if (!sessionId || state.mapHistory.deleting) return
  const confirmed = window.confirm(`确定删除地图“${sessionName || sessionId}”吗？此操作不能撤销。`)
  if (!confirmed) return
  state.mapHistory.deleting = sessionId
  renderMapHistory({ sessions: state.mapHistory.sessions })
  try {
    const response = await fetch(`/api/maps/session?id=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
    if (!response.ok) throw new Error('delete failed')
    await loadMapHistory()
    updateMappingControls()
  } catch (error) {
    updateMappingMessage('删除失败，请稍后重试')
  } finally {
    state.mapHistory.deleting = ''
    renderMapHistory({ sessions: state.mapHistory.sessions })
  }
}

async function rerunMapPostprocess(sessionId) {
  if (!sessionId || state.mapHistory.postprocessing) return
  const preset = postprocessPresetForSession(sessionId, findMapSession(sessionId))
  state.mapHistory.postprocessing = sessionId
  renderMapHistory({ sessions: state.mapHistory.sessions })
  updateMappingMessage(`正在重跑后处理：${postprocessPresetLabel(preset) || '默认'}`)
  try {
    const response = await fetch(`/api/maps/postprocess?id=${encodeURIComponent(sessionId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok || payload.ok === false) throw new Error(payload.message || 'postprocess failed')
    const session = await waitForPostprocessRefresh(sessionId)
    const postprocess = session?.postprocess || {}
    if (!session || postprocess.state === 'failed') {
      throw new Error(postprocess.message || 'postprocess failed')
    }
    updateMappingMessage(`后处理已重跑：${postprocessPresetLabel(preset) || '默认'}`)
  } catch (error) {
    updateMappingMessage('后处理重跑失败')
  } finally {
    state.mapHistory.postprocessing = ''
    await loadMapHistory()
    renderMapHistory({ sessions: state.mapHistory.sessions })
  }
}

async function waitForPostprocessRefresh(sessionId) {
  const before = findMapSession(sessionId)
  const beforeVersion = mapSessionVersion(before)
  for (let attempt = 0; attempt < SAVE_DOWNLOAD_ATTEMPTS; attempt += 1) {
    await loadMapHistory()
    const session = findMapSession(sessionId)
    if (session && mapSessionVersion(session) > beforeVersion) return session
    await sleep(SAVE_DOWNLOAD_INTERVAL_MS)
  }
  return null
}

function mapFileLabel(filename) {
  if (isGlobalOptimizedMapFile(filename)) return '后处理地图'
  if (isAccumulatedMapFile(filename)) return '里程计地图'
  if (isLegacyBackendMapFile(filename)) return 'FAST-LIO 兼容地图'
  if (isFrontendMapFile(filename)) return '里程计地图'
  if (filename === 'poses_tum.txt') return 'TUM 位姿'
  if (filename === 'poses_kitti.txt') return 'KITTI 位姿'
  if (filename === 'poses_matrix.txt') return '矩阵位姿'
  return filename
}

function isGlobalOptimizedMapFile(filename) {
  return filename.endsWith('_global_optimized_map.pcd')
}

function isAccumulatedMapFile(filename) {
  return filename.endsWith('_accumulated_map.pcd')
}

function isLegacyBackendMapFile(filename) {
  return filename.endsWith('_map.pcd') && !isGlobalOptimizedMapFile(filename)
}

function isFrontendMapFile(filename) {
  return filename.endsWith('_frontend.pcd')
}

function setStatePill(element, stateText) {
  if (!element) return
  const next = stateText || 'waiting'
  element.textContent = next
  element.classList.remove('is-online', 'is-stale', 'is-waiting', 'is-disconnected')
  element.classList.add(statePillClass(next))
}

function statePillClass(stateText) {
  if (stateText === 'online') return 'is-online'
  if (stateText === 'stale') return 'is-stale'
  if (stateText === 'disconnected' || stateText === 'invalid' || stateText === 'timeout' || stateText === 'error') return 'is-disconnected'
  return 'is-waiting'
}

function setConnectionPill(stateText) {
  if (!ui.wsState) return
  const next = stateText || 'connecting'
  ui.wsState.textContent = next
  ui.wsState.classList.remove('is-online', 'is-stale', 'is-waiting', 'is-disconnected')
  const className = next === 'connected'
    ? 'is-online'
    : next === 'disconnected'
      ? 'is-disconnected'
      : 'is-waiting'
  ui.wsState.classList.add(className)
}

function connectionStateFromHealth(healthState) {
  if (healthState === 'online') return 'connected'
  if (healthState === 'waiting') return 'connecting'
  return 'disconnected'
}

function sensorHealth(topics, lidarState) {
  return lidarState || topics.raw?.state || 'disconnected'
}

function resetLiveStats() {
  state.liveStats = {}
}

function recordLiveStat(key, payload = {}) {
  state.liveStats[key] = {
    receivedAt: performance.now(),
    stampSec: Number(payload.stamp_sec),
  }
}

function refreshLiveStats(topics) {
  const now = performance.now()
  for (const [key, stat] of Object.entries(topics)) {
    if (!stat || stat.state !== 'online') continue
    if (!state.liveStats[key]) {
      const ageSec = Number(stat.age_sec)
      state.liveStats[key] = {
        receivedAt: Number.isFinite(ageSec) ? now - ageSec * 1000 : now,
        stampSec: Number(stat.last_stamp_sec),
      }
    }
  }
}

function liveAgeSec(key, stat) {
  if (stat?.state !== 'online') return null
  const live = state.liveStats[key]
  if (!live || !Number.isFinite(live.receivedAt)) return Number.isFinite(stat.age_sec) ? stat.age_sec : null
  const ageMs = performance.now() - live.receivedAt
  if (ageMs < 0 || ageMs > LIVE_STAT_STALE_MS) return Number.isFinite(stat.age_sec) ? stat.age_sec : null
  return ageMs / 1000
}

function formatStatAge(stat, key) {
  return formatAge(liveAgeSec(key, stat))
}

function latestDataAge(items) {
  const ages = items
    .map(([stat, key]) => liveAgeSec(key, stat))
    .filter((age) => Number.isFinite(age))
  if (ages.length === 0) return '-'
  return formatAge(Math.min(...ages))
}

function formatAge(value) {
  if (!Number.isFinite(value)) return '-'
  if (value < 1) return `${Math.round(value * 1000)} ms`
  return `${Number(value).toFixed(1)} s`
}

function updatePipelineStatus(topics) {
  for (const source of SOURCES) {
    setLayerButtonStatus(source, topics[source] || {})
  }
}

function updateBackendDetails(topics) {
  for (const row of ui.backendTopicRows) {
    const stat = topics[row.dataset.topicKey] || {}
    const stateText = stat.state || 'waiting'
    const stateEl = row.querySelector('.topic-state')
    const metaEl = row.querySelector('.topic-meta')
    if (stateEl) {
      stateEl.textContent = stateText
      stateEl.className = `topic-state is-${stateText}`
    }
    if (metaEl) metaEl.textContent = topicMeta(stat)
    row.title = stat.topic ? `${stat.topic} ${stateText}` : stateText
  }
}

function topicMeta(stat) {
  if (!stat.topic) return '-'
  const parts = [stat.topic]
  if (Number.isFinite(stat.hz)) parts.push(`${formatHz(stat.hz)} Hz`)
  if (Number.isFinite(stat.age_sec)) parts.push(`age ${Number(stat.age_sec).toFixed(1)}s`)
  if (Number.isFinite(stat.last_points) && stat.last_points > 0) {
    parts.push(`${compact(stat.last_points)} pts`)
  }
  if (
    Number.isFinite(stat.last_sampled_points)
    && stat.last_sampled_points > 0
    && stat.last_sampled_points !== stat.last_points
  ) {
    parts.push(`${compact(stat.last_sampled_points)} shown`)
  }
  return parts.join(' · ')
}

function setLayerButtonStatus(source, stat) {
  const button = ui.layerToggles.find((item) => item.dataset.source === source)
  if (!button) return
  const stateText = stat.state || 'waiting'
  const online = stateText === 'online'
  const selected = state.visibleSources.has(source)
  const hasCachedPoints = (state.layers[source]?.pointCount || 0) > 0
  button.classList.toggle('is-available', online)
  button.classList.toggle('has-cache', hasCachedPoints)
  button.classList.toggle('is-unavailable', !online)
  button.classList.toggle('is-standby', online && !selected)
  button.disabled = !online && !hasCachedPoints
  button.setAttribute('aria-disabled', String(button.disabled))
  button.title = `${SOURCE_LABELS[source]}: ${stateText}${stat.topic ? ` (${stat.topic})` : ''}`
  const status = button.querySelector('.layer-status')
  if (status) {
    status.textContent = online ? `${formatHz(stat.hz)} Hz` : stateText
  }
}

function updatePose(payload) {
  if (state.mapHistory.savedPreviewActive) return
  state.pose = payload
  if (state.followPose && Number.isFinite(payload.x) && Number.isFinite(payload.y) && Number.isFinite(payload.z)) {
    setControlsTarget([payload.x, payload.y, payload.z], true)
  }
  updatePoseObject()
  const yawDeg = Number.isFinite(payload.yaw) ? (payload.yaw * 180) / Math.PI : null
  ui.poseX.textContent = fmt(payload.x)
  ui.poseY.textContent = fmt(payload.y)
  ui.poseZ.textContent = fmt(payload.z)
  ui.poseYaw.textContent = yawDeg === null ? '-' : fmt(yawDeg)
  ui.poseFrame.textContent = payload.frame_id || '-'
  ui.poseReadout.innerHTML = [
    metricLine('X', fmt(payload.x), 'm'),
    metricLine('Y', fmt(payload.y), 'm'),
    metricLine('Z', fmt(payload.z), 'm'),
    metricLine('Yaw', yawDeg === null ? '-' : fmt(yawDeg), 'deg'),
  ].join('')
}

function updateImu(payload) {
  state.imu = payload
  const accel = payload.linear_acceleration || []
  const gyro = payload.angular_velocity || []
  const accelNorm = Number.isFinite(payload.accel_norm) ? payload.accel_norm : vectorNorm(accel)
  const gyroNorm = Number.isFinite(payload.gyro_norm) ? payload.gyro_norm : vectorNorm(gyro)
  ui.imuAccelNorm.textContent = fmt(accelNorm)
  ui.imuGyroNorm.textContent = fmt(gyroNorm)
  ui.imuFrame.textContent = payload.frame_id || '-'
  ui.imuReadout.innerHTML = [
    metricLine('Acc X', fmt(accel[0]), 'm/s2'),
    metricLine('Acc Y', fmt(accel[1]), 'm/s2'),
    metricLine('Acc Z', fmt(accel[2]), 'm/s2'),
    metricLine('|Acc|', fmt(accelNorm), 'm/s2'),
    metricLine('Gyro X', fmt(gyro[0]), 'rad/s'),
    metricLine('Gyro Y', fmt(gyro[1]), 'rad/s'),
    metricLine('Gyro Z', fmt(gyro[2]), 'rad/s'),
    metricLine('|Gyro|', fmt(gyroNorm), 'rad/s'),
  ].join('')
}

function metricLine(label, value, unit) {
  return `<div class="metric-line"><span>${label}</span><strong>${value}</strong><em>${unit}</em></div>`
}

function updatePoseObject() {
  if (!state.pose || !Number.isFinite(state.pose.x)) return
  const p = [state.pose.x, state.pose.y, state.pose.z]
  const yaw = Number.isFinite(state.pose.yaw) ? state.pose.yaw : 0
  const tip = [p[0] + Math.cos(yaw) * 1.2, p[1] + Math.sin(yaw) * 1.2, p[2]]
  const positions = new Float32Array([
    p[0] - 0.4, p[1], p[2], p[0] + 0.4, p[1], p[2],
    p[0], p[1] - 0.4, p[2], p[0], p[1] + 0.4, p[2],
    p[0], p[1], p[2], tip[0], tip[1], tip[2],
  ])
  const colors = new Float32Array([
    1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1,
    1, 0.84, 0.24, 1, 0.84, 0.24,
  ])
  poseGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  poseGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  poseMarker.position.set(p[0], p[1], p[2])
  poseMarker.visible = true
}

function updatePath(payload) {
  if (state.mapHistory.savedPreviewActive) return
  if (payload.source === 'raw' || payload.source === 'optimized') {
    const sourcePointCount = Number.isFinite(payload.source_point_count)
      ? payload.source_point_count
      : (payload.points || []).length
    state.pathSourceCounts[payload.source] = sourcePointCount
    state.paths[payload.source] = visiblePathPointsAfterClear(
      payload.points || [],
      sourcePointCount,
      state.pathClearSourceCounts[payload.source] || 0,
    )
    updatePathObject(payload.source)
    updateTrajectoryControls()
  }
}

function visiblePathPointsAfterClear(points, sourcePointCount, clearSourcePointCount) {
  if (!clearSourcePointCount || sourcePointCount <= clearSourcePointCount) return clearSourcePointCount ? [] : points
  if (!points.length) return points
  const sampleEvery = Math.max(1, Math.ceil(sourcePointCount / points.length))
  const hiddenPointCount = Math.min(points.length, Math.ceil(clearSourcePointCount / sampleEvery))
  return points.slice(hiddenPointCount)
}

function updatePathObject(source) {
  const points = state.paths[source] || []
  if (pathLines[source]) {
    scene.remove(pathLines[source])
    pathLines[source].geometry.dispose()
    pathLines[source].material.dispose()
    pathLines[source] = null
  }
  if (points.length < 2) {
    syncPathVisibility()
    return
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(
    points.map((point) => new THREE.Vector3(point[0], point[1], point[2])),
  )
  const material = new THREE.LineBasicMaterial({
    color: SCENE.trajectory,
    transparent: true,
    opacity: 0.92,
    toneMapped: false,
  })
  pathLines[source] = new THREE.Line(geometry, material)
  scene.add(pathLines[source])
  syncPathVisibility()
}

function syncPathVisibility() {
  if (pathLines.raw) pathLines.raw.visible = state.trajectoryVisible && state.visibleSources.has('raw')
  if (pathLines.optimized) pathLines.optimized.visible = state.trajectoryVisible && state.visibleSources.has('optimized')
}

function hasVisibleTrajectory() {
  return ['raw', 'optimized'].some((source) => (
    state.trajectoryVisible
    && state.visibleSources.has(source)
    && (state.paths[source]?.length || 0) >= 2
  ))
}

function updateTrajectoryControls() {
  if (ui.clearTrajectory) ui.clearTrajectory.disabled = !hasVisibleTrajectory()
  if (!ui.toggleTrajectory) return
  ui.toggleTrajectory.classList.toggle('is-active', state.trajectoryVisible)
  ui.toggleTrajectory.setAttribute('aria-pressed', String(state.trajectoryVisible))
  ui.toggleTrajectory.textContent = state.trajectoryVisible ? '隐藏轨迹' : '显示轨迹'
}

function toggleTrajectoryVisibility() {
  state.trajectoryVisible = !state.trajectoryVisible
  syncPathVisibility()
  updateTrajectoryControls()
}

function updatePointUi() {
  const totalPoints = CLOUD_SOURCES.reduce((sum, source) => {
    if (!state.visibleSources.has(source)) return sum
    return sum + (state.layers[source]?.pointCount || 0)
  }, 0)
  ui.pointSizeValue.textContent = `${state.pointSize.toFixed(1)} px`
  ui.pointBudgetValue.textContent = state.pointBudget >= UNLIMITED_POINT_BUDGET ? '全部' : compact(state.pointBudget)
  ui.bufferPoints.textContent = compact(totalPoints)
  ui.mapPoints.textContent = compact(state.layers.map?.pointCount || 0)
  ui.optimizedPoints.textContent = compact(state.layers.optimized?.pointCount || 0)
  ui.rawPoints.textContent = compact(state.layers.raw?.pointCount || 0)
}

function toggleLayer(source) {
  if (!SOURCES.includes(source)) return
  const button = ui.layerToggles.find((item) => item.dataset.source === source)
  if (button?.disabled) return
  if (state.visibleSources.has(source)) {
    state.visibleSources.delete(source)
  } else {
    state.visibleSources.add(source)
  }
  syncLayerVisibility()
  syncLayerButtons()
  syncPathVisibility()
  requestAllSources()
  updatePointUi()
  updateTrajectoryControls()
}

function syncLayerVisibility() {
  for (const source of SOURCES) {
    if (state.layers[source]) state.layers[source].object.visible = state.visibleSources.has(source)
  }
}

function syncLayerButtons() {
  for (const button of ui.layerToggles) {
    const source = button.dataset.source
    const active = state.visibleSources.has(source)
    button.classList.toggle('is-active', active)
    button.classList.toggle('is-standby', button.classList.contains('is-available') && !active)
    button.setAttribute('aria-pressed', String(active))
  }
}

function clearCloud() {
  state.mapHistory.savedPreviewActive = false
  state.mapHistory.activePreviewId = ''
  for (const source of CLOUD_SOURCES) {
    clearSourceLayer(source)
  }
  state.bounds = null
  state.latestFramePoints = 0
  renderMapHistory({ sessions: state.mapHistory.sessions })
  updatePointUi()
  updateMappingControls()
  updateMappingMessage()
}

function clearTrajectory(options = {}) {
  const { clearPose = false, resetCutoff = false } = options
  for (const source of ['raw', 'optimized']) {
    state.pathClearSourceCounts[source] = resetCutoff ? 0 : state.pathSourceCounts[source]
    state.paths[source] = []
    updatePathObject(source)
  }
  if (clearPose) {
    state.pose = null
    if (poseMarker) poseMarker.visible = false
    if (poseGeometry) {
      poseGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(0), 3))
      poseGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(0), 3))
    }
  }
  updateTrajectoryControls()
}

function resetLiveMappingScene() {
  state.mapHistory.savedPreviewActive = false
  state.mapHistory.activePreviewId = ''
  for (const source of CLOUD_SOURCES) {
    clearSourceLayer(source)
  }
  clearTrajectory({ clearPose: true, resetCutoff: true })
  state.bounds = null
  state.latestFramePoints = 0
  renderMapHistory({ sessions: state.mapHistory.sessions })
  updatePointUi()
  updateMappingControls()
  updateMappingMessage()
}

function clearSavedMapLayers() {
  for (const source of SAVED_MAP_SOURCES) {
    clearSourceLayer(source)
  }
}

function clearSourceLayer(source) {
  const layer = state.layers[source]
  if (!layer) return
  layer.positions = new Float32Array(0)
  layer.colors = new Float32Array(0)
  layer.pointCount = 0
  layer.framePointCount = 0
  layer.sourcePointCount = 0
  layer.bounds = null
  uploadLayer(layer)
  state.bounds = recomputeBounds()
  state.latestFramePoints = 0
}

function recenterCamera(bounds, source) {
  const totalPoints = CLOUD_SOURCES.reduce((sum, key) => sum + (state.layers[key]?.pointCount || 0), 0)
  if (!bounds || totalPoints > state.latestFramePoints || state.followPose) return
  if (source === 'raw') return
  const target = boundsCenter(bounds)
  const span = boundsSpan(bounds)
  setView(target, Math.max(8, Math.min(240, span * 1.8)))
}

function setView(target, distance) {
  const direction = new THREE.Vector3(13, 12, 9).normalize().multiplyScalar(distance)
  camera.up.set(0, 0, 1)
  controls.target.set(target[0], target[1], target[2])
  camera.position.copy(controls.target).add(direction)
  controls.update()
}

function setControlsTarget(target, preserveOffset) {
  const offset = camera.position.clone().sub(controls.target)
  controls.target.set(target[0], target[1], target[2])
  if (preserveOffset) {
    camera.position.copy(controls.target).add(offset)
  }
  controls.update()
}

function resetCameraView() {
  const target = state.bounds ? boundsCenter(state.bounds) : state.pose && Number.isFinite(state.pose.x)
    ? [state.pose.x, state.pose.y, state.pose.z]
    : [0, 0, 0]
  const span = state.bounds ? boundsSpan(state.bounds) : 20
  state.followPose = false
  updateFollowButton()
  setView(target, Math.max(8, Math.min(240, span * 1.8)))
}

function toggleFollowPose() {
  state.followPose = !state.followPose
  if (state.followPose && state.pose && Number.isFinite(state.pose.x)) {
    setControlsTarget([state.pose.x, state.pose.y, state.pose.z], true)
  }
  updateFollowButton()
}

function updateFollowButton() {
  ui.followPose.classList.toggle('is-active', state.followPose)
  ui.followPose.setAttribute('aria-pressed', String(state.followPose))
  ui.resetView.disabled = state.followPose
}

function resizeRenderer() {
  const width = Math.max(1, canvas.clientWidth)
  const height = Math.max(1, canvas.clientHeight)
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()

  if (gizmoRenderer) {
    const size = 112
    gizmoRenderer.setSize(size, size, false)
    gizmoCamera.aspect = 1
    gizmoCamera.updateProjectionMatrix()
  }
}

function startRenderLoop() {
  if (state.renderLoopRunning) return
  state.renderLoopRunning = true
  state.renderFrameCount = 0
  state.renderFpsLastAt = null
  requestAnimationFrame(render)
}

function render() {
  if (!state.renderLoopRunning) return
  resizeRenderer()
  controls.update()
  renderer.render(scene, camera)
  renderGizmo()
  updateRenderFps()
  requestAnimationFrame(render)
}

function updateRenderFps() {
  if (state.renderFpsLastAt === null) {
    state.renderFpsLastAt = performance.now()
    return
  }
  state.renderFrameCount += 1
  const now = performance.now()
  const elapsed = now - state.renderFpsLastAt
  if (elapsed < 200) return
  const nextFps = (state.renderFrameCount / elapsed) * 1000
  state.renderFrameCount = 0
  state.renderFpsLastAt = now
  ui.hudFrame.textContent = `FPS ${nextFps.toFixed(0)}`
}

function renderGizmo() {
  if (!gizmoRenderer || !gizmoScene || !gizmoCamera) return
  const direction = camera.position.clone().sub(controls.target).normalize().multiplyScalar(4)
  gizmoCamera.position.copy(direction)
  gizmoCamera.up.copy(camera.up)
  gizmoCamera.lookAt(0, 0, 0)
  gizmoRenderer.render(gizmoScene, gizmoCamera)
}

for (const button of ui.layerToggles) {
  button.addEventListener('click', () => toggleLayer(button.dataset.source))
}

for (const button of ui.sectionToggles) {
  button.addEventListener('click', () => {
    const section = button.closest('.panel-section')
    if (!section) return
    const collapsed = section.classList.toggle('is-collapsed')
    button.setAttribute('aria-expanded', String(!collapsed))
  })
}

ui.layerSettingsToggle.addEventListener('click', () => {
  setLayerSettingsOpen(ui.layerSettingsPopover.hidden)
})

document.addEventListener('pointerdown', (event) => {
  if (ui.layerSettingsPopover.hidden) return
  const target = event.target
  if (ui.layerSettingsPopover.contains(target) || ui.layerSettingsToggle.contains(target)) return
  setLayerSettingsOpen(false)
})

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape' || ui.layerSettingsPopover.hidden) return
  setLayerSettingsOpen(false)
  ui.layerSettingsToggle.focus()
})

function setLayerSettingsOpen(open) {
  ui.layerSettingsPopover.hidden = !open
  ui.layerSettingsToggle.classList.toggle('is-open', open)
  ui.layerSettingsToggle.setAttribute('aria-expanded', String(open))
}

ui.pointSize.addEventListener('input', () => {
  state.pointSize = Number(ui.pointSize.value)
  for (const source of CLOUD_SOURCES) {
    state.layers[source].material.size = pointSizeForSource(source)
  }
  updatePointUi()
})

ui.pointBudget.addEventListener('input', () => {
  state.pointBudget = Number(ui.pointBudget.value)
  trimLayersToBudget()
  updatePointUi()
})

ui.clearCloud.addEventListener('click', clearCloud)
ui.toggleTrajectory.addEventListener('click', toggleTrajectoryVisibility)
ui.clearTrajectory.addEventListener('click', () => clearTrajectory())
ui.resetView.addEventListener('click', resetCameraView)
ui.followPose.addEventListener('click', toggleFollowPose)
ui.startLidar.addEventListener('click', () => sendMappingCommand('start_lidar'))
ui.stopLidar.addEventListener('click', () => sendMappingCommand('stop_lidar'))
ui.checkLidar.addEventListener('click', () => sendMappingCommand('check_lidar'))
ui.startMapping.addEventListener('click', () => sendMappingCommand('start'))
ui.stopMapping.addEventListener('click', () => sendMappingCommand('stop'))
ui.refreshHistory.addEventListener('click', loadMapHistory)
ui.historyPreviewSelected.addEventListener('click', () => previewMapSession(state.mapHistory.selectedSessionId))
ui.historyDeleteSelected.addEventListener('click', () => {
  const session = selectedMapSession()
  if (!session) return
  deleteMapSession(session.id || session.name, session.name)
})
ui.historyPostprocessSelected.addEventListener('click', () => rerunMapPostprocess(state.mapHistory.selectedSessionId))
ui.historyPostprocessPreset.addEventListener('change', () => {
  const sessionId = state.mapHistory.selectedSessionId
  if (!sessionId) return
  state.mapHistory.postprocessPresets[sessionId] = ui.historyPostprocessPreset.value || 'default'
})
ui.historyDownloadSelected.addEventListener('click', (event) => {
  const session = selectedMapSession()
  const disabled = ui.historyDownloadSelected.getAttribute('aria-disabled') === 'true'
  if (!session || disabled) {
    event.preventDefault()
    return
  }
  event.preventDefault()
  downloadMapArchive(session)
})
ui.historyList.addEventListener('click', (event) => {
  const row = event.target.closest('.history-file-row')
  const item = event.target.closest('.history-item')
  const sessionId = row?.dataset.sessionId || item?.dataset.sessionId || ''
  if (!sessionId) return
  const wasSelected = state.mapHistory.selectedSessionId === sessionId
  if (row || !wasSelected) {
    event.preventDefault()
  }
  selectMapSession(sessionId)
})
window.addEventListener('resize', resizeRenderer)

function trimLayersToBudget() {
  for (const source of CLOUD_SOURCES) {
    const layer = state.layers[source]
    const budget = sourceBudget(source)
    if (!Number.isFinite(budget)) continue
    if (layer.pointCount <= budget) continue
    const start = layer.pointCount - budget
    layer.positions = layer.positions.subarray(start * 3).slice()
    layer.colors = layer.colors.subarray(start * 3).slice()
    layer.pointCount = budget
    uploadLayer(layer)
  }
  updateMappingControls()
  updateMappingMessage()
}

function unionBounds(a, b) {
  if (!b) return a
  if (!a) return { min: [...b.min], max: [...b.max] }
  return {
    min: [
      Math.min(a.min[0], b.min[0]),
      Math.min(a.min[1], b.min[1]),
      Math.min(a.min[2], b.min[2]),
    ],
    max: [
      Math.max(a.max[0], b.max[0]),
      Math.max(a.max[1], b.max[1]),
      Math.max(a.max[2], b.max[2]),
    ],
  }
}

function recomputeBounds() {
  let bounds = null
  for (const source of CLOUD_SOURCES) {
    const layer = state.layers[source]
    if (!layer?.bounds || layer.pointCount <= 0) continue
    bounds = unionBounds(bounds, layer.bounds)
  }
  return bounds
}

function boundsCenter(bounds) {
  return [
    (bounds.min[0] + bounds.max[0]) * 0.5,
    (bounds.min[1] + bounds.max[1]) * 0.5,
    (bounds.min[2] + bounds.max[2]) * 0.5,
  ]
}

function boundsSpan(bounds) {
  return Math.max(
    bounds.max[0] - bounds.min[0],
    bounds.max[1] - bounds.min[1],
    bounds.max[2] - bounds.min[2],
  )
}

function formatHz(value) {
  return Number.isFinite(value) ? Number(value).toFixed(value >= 10 ? 1 : 2) : '0.00'
}

function fmt(value) {
  return Number.isFinite(value) ? Number(value).toFixed(3) : '-'
}

function formatNumber(value, digits = 2) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : '-'
}

function formatSeconds(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return '-'
  if (numeric < 1) return `${Math.round(numeric * 1000)} ms`
  return `${numeric.toFixed(numeric >= 10 ? 1 : 2)} s`
}

function compact(value) {
  if (!Number.isFinite(value)) return '0'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return String(value)
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char])
}

function escapeAttr(value) {
  return escapeHtml(value)
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function vectorNorm(values) {
  if (!Array.isArray(values) || values.length === 0) return NaN
  return Math.sqrt(values.reduce((sum, value) => sum + Number(value) * Number(value), 0))
}

function startApp() {
  document.querySelector('#saveMapping')?.remove()
  updateMappingControls()
  updateMappingMessage()
  updateTrajectoryControls()
  try {
    initThree()
    connect()
    loadMapHistory()
    startRenderLoop()
  } catch (error) {
    console.error('WebGL initialization failed; mapping controls remain available.', error)
    connect()
    loadMapHistory()
  }
}

startApp()
