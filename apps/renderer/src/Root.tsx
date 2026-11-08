import React from 'react';
import {Composition, type CalculateMetadataFunction} from 'remotion';
import {IdeaToVideo} from './Video';
import type {VideoProps} from './types';

const defaultProps: VideoProps = {
  title: 'Một ý tưởng, một câu chuyện',
  projectName: 'Dự án mới',
  template: 'cinematic',
  aspectRatio: '9:16',
  durationSeconds: 10,
  scenes: [{id: 1, scene_title: 'Câu chuyện bắt đầu', narration: '', visual_prompt: '', key_points: ['Nội dung sẽ hiển thị tại đây'], start: 0, end: 10, duration: 10, audio_src: ''}],
  sentences: [],
  audioTracks: [],
};

const calculateMetadata: CalculateMetadataFunction<VideoProps> = ({props}) => {
  const [width, height] = props.aspectRatio === '16:9' ? [1920, 1080] : props.aspectRatio === '1:1' ? [1080, 1080] : [1080, 1920];
  return {
    width,
    height,
    fps: 30,
    durationInFrames: Math.max(1, Math.ceil(props.durationSeconds * 30)),
  };
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="IdeaToVideo"
      component={IdeaToVideo}
      durationInFrames={300}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  </>
);
