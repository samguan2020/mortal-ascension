export const world = {
  bounds: { x: 8.2, z: 6.2 },
  speed: 4.2,
  interactionRange: 2.35,
  actorHeight: 2.65,
  playerStart: [-2.8, 0, 2.5] as const,
  npcStart: [2.2, 0, -1.1] as const,
  cameraOffset: [8, 10, 12] as const,
  playerAsset: "/characters/player_traveler_animated.glb",
  npcAsset: "/characters/liu_innkeeper_animated.glb",
  npcName: "柳掌柜",
  palette: {
    sky: 0xb4dfe9, mist: 0xc4e7ed, plaster: 0xf0e7cd,
    beams: 0x633b2b, boards: 0xa76d41, table: 0xb87d4a,
    teal: 0x278b8e, red: 0xc84b48, paper: 0xd9f6ec,
  },
};

export const text = {
  online: "AI 掌柜已连接",
  offline: "AI 服务暂不可用",
  actors: "旅人行走 · 掌柜交谈手势",
  greeting: "客官里面请。外头雨大，先坐下喝碗热茶吧。想打听什么，不妨问问。",
  thinking: "柳掌柜正在斟酌…",
  failed: "暂时没能得到回复，请稍后重试。",
  initFailed: "游戏未能完整加载，请刷新页面重试。",
  gpu: "WebGPU",
  gl: "WebGL 2",
};
