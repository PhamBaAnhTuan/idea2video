export type Scene = {
  id: number;
  scene_title: string;
  narration: string;
  visual_prompt: string;
  key_points: string[];
  start: number;
  end: number;
  duration: number;
  audio_src: string;
};

export type Sentence = {
  id: number;
  scene_id: number;
  start: number;
  end: number;
  text: string;
};

export type AudioTrack = {
  src: string;
  start: number;
  duration: number;
};

export type VideoProps = {
  title: string;
  projectName: string;
  template: 'cinematic' | 'captions' | 'bullet_list' | 'table' | 'chart';
  aspectRatio: '9:16' | '16:9' | '1:1';
  durationSeconds: number;
  scenes: Scene[];
  sentences: Sentence[];
  audioTracks: AudioTrack[];
};
