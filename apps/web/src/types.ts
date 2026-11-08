export type Project = {
  id: string;
  name?: string;
  video_template?: 'cinematic' | 'captions' | 'bullet_list' | 'table' | 'chart';
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage: string;
  progress: number;
  current_step?: 'script' | 'tts' | 'alignment' | 'timeline' | 'render' | null;
  steps?: Partial<Record<'script' | 'tts' | 'alignment' | 'timeline' | 'render', 'pending' | 'running' | 'completed' | 'skipped' | 'failed'>>;
  error?: string | null;
  script?: {
    video_title: string;
    hook: string;
    scenes: {id: number; scene_title: string; narration: string; visual_prompt: string; key_points: string[]}[];
  } | null;
  timeline?: {
    duration_seconds: number;
    scenes: {id: number; start: number; end: number; scene_title: string}[];
    sentences: {id: number; scene_id: number; start: number; end: number; text: string}[];
  } | null;
  artifacts?: Record<string, string>;
};

export type ProjectSummary = {
  id: string;
  name: string;
  status: Project['status'];
  stage: string;
  progress: number;
  created_at: string;
  updated_at: string;
  video_template: NonNullable<Project['video_template']>;
};
