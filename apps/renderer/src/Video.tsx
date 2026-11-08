import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import type {Scene, Sentence, VideoProps} from './types';

const PALETTES = [
  ['#101b3b', '#263b70', '#f59e0b'],
  ['#102c2b', '#176b68', '#f7b267'],
  ['#2d183b', '#6b3b73', '#f4a261'],
  ['#172033', '#384d6b', '#8ecae6'],
  ['#2b1d17', '#784b32', '#e9c46a'],
  ['#14213d', '#315b85', '#fca311'],
];

const scenePoints = (scene: Scene) => {
  const points = scene.key_points.filter(point => point.trim());
  if (points.length) return points.slice(0, 5);
  return scene.narration.split(/(?<=[.!?])\s+/).filter(Boolean).slice(0, 4);
};

const SceneCard: React.FC<{
  scene: Scene;
  index: number;
  title: string;
  projectName: string;
  template: VideoProps['template'];
  allScenes: Scene[];
}> = ({scene, index, title, projectName, template, allScenes}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const palette = PALETTES[index % PALETTES.length];
  const enter = interpolate(frame, [0, 18], [0, 1], {extrapolateRight: 'clamp'});
  const drift = interpolate(frame, [0, fps * 8], [0, -28], {extrapolateRight: 'clamp'});
  const compact = width < height;
  const points = scenePoints(scene);
  const commonStyle: React.CSSProperties = {
    opacity: enter,
    overflow: 'hidden',
    padding: compact ? '9% 8% 24%' : '7% 9% 20%',
    color: '#fff',
    background: `radial-gradient(circle at 82% 18%, ${palette[1]} 0%, transparent 42%), linear-gradient(135deg, ${palette[0]}, #080d19 78%)`,
    fontFamily: 'Arial, Helvetica, sans-serif',
  };
  const header = (
    <div style={{display: 'flex', alignItems: 'center', gap: 14, marginBottom: compact ? 48 : 32, opacity: 0.9}}>
      <div style={{width: 42, height: 5, borderRadius: 9, background: palette[2]}} />
      <div style={{fontSize: compact ? 21 : 18, letterSpacing: 3, textTransform: 'uppercase'}}>{projectName} · {String(scene.id).padStart(2, '0')}</div>
    </div>
  );

  if (template !== 'cinematic') {
    const titleStyle: React.CSSProperties = {
      fontSize: compact ? 61 : 54,
      fontWeight: 800,
      lineHeight: 1.08,
      margin: 0,
      textWrap: 'balance',
      textShadow: '0 8px 35px #0008',
    };
    const panelStyle: React.CSSProperties = {
      marginTop: compact ? 48 : 34,
      padding: compact ? 28 : 22,
      borderRadius: 24,
      background: 'rgba(5, 11, 24, 0.58)',
      border: `1px solid ${palette[2]}66`,
      boxShadow: '0 22px 65px #0005',
    };

    return (
      <AbsoluteFill style={commonStyle}>
        <div style={{position: 'absolute', width: width * 0.68, height: width * 0.68, borderRadius: '50%', border: `1px solid ${palette[2]}44`, right: -width * 0.28, top: -width * 0.12, transform: `translateY(${drift}px)`}} />
        {header}
        <div style={{fontSize: compact ? 22 : 17, color: palette[2], letterSpacing: 4, textTransform: 'uppercase', marginBottom: 20}}>{title}</div>
        <h1 style={titleStyle}>{scene.scene_title}</h1>
        {template === 'captions' && (
          <div style={{...panelStyle, marginTop: compact ? 62 : 44, fontSize: compact ? 33 : 27, lineHeight: 1.45, borderLeft: `7px solid ${palette[2]}`}}>
            {scene.narration}
          </div>
        )}
        {template === 'bullet_list' && (
          <div style={panelStyle}>
            <div style={{fontSize: compact ? 19 : 15, letterSpacing: 3, color: palette[2], marginBottom: 26}}>Ý CHÍNH</div>
            <div style={{display: 'flex', flexDirection: 'column', gap: compact ? 27 : 20}}>
              {points.map((point, pointIndex) => (
                <div key={pointIndex} style={{display: 'flex', gap: 18, alignItems: 'flex-start', fontSize: compact ? 31 : 25, lineHeight: 1.32}}>
                  <span style={{color: palette[2], fontWeight: 800}}>{String(pointIndex + 1).padStart(2, '0')}</span><span>{point}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {template === 'table' && (
          <div style={panelStyle}>
            <div style={{fontSize: compact ? 19 : 15, letterSpacing: 3, color: palette[2], marginBottom: 20}}>BẢNG TÓM TẮT</div>
            <div style={{display: 'grid', gridTemplateColumns: '0.27fr 1fr', color: '#aebbd0', fontSize: compact ? 18 : 15, borderBottom: '1px solid #ffffff33', paddingBottom: 12, marginBottom: 6}}>
              <span>STT</span><span>NỘI DUNG</span>
            </div>
            {points.map((point, pointIndex) => (
              <div key={pointIndex} style={{display: 'grid', gridTemplateColumns: '0.27fr 1fr', gap: 12, alignItems: 'start', padding: compact ? '19px 0' : '14px 0', borderBottom: '1px solid #ffffff1c', fontSize: compact ? 27 : 22, lineHeight: 1.3}}>
                <span style={{color: palette[2], fontWeight: 800}}>{String(pointIndex + 1).padStart(2, '0')}</span><span>{point}</span>
              </div>
            ))}
          </div>
        )}
        {template === 'chart' && (() => {
          const visibleScenes = allScenes.length <= 6
            ? allScenes
            : allScenes.slice(Math.max(0, Math.min(index - 2, allScenes.length - 6)), Math.max(0, Math.min(index - 2, allScenes.length - 6)) + 6);
          const maxDuration = Math.max(...visibleScenes.map(item => item.duration), 1);
          return (
            <div style={panelStyle}>
              <div style={{fontSize: compact ? 19 : 15, letterSpacing: 3, color: palette[2], marginBottom: 12}}>NHỊP ĐỘ CÁC CẢNH</div>
              <div style={{fontSize: compact ? 20 : 16, color: '#b5c2d5', marginBottom: 22}}>Thời lượng audio · giây</div>
              <div style={{display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: compact ? 14 : 22, height: compact ? height * 0.3 : height * 0.36}}>
                {visibleScenes.map(item => {
                  const isCurrent = item.id === scene.id;
                  const barHeight = Math.max(16, item.duration / maxDuration * (compact ? height * 0.24 : height * 0.3));
                  return (
                    <div key={item.id} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', gap: 10, height: '100%', flex: 1, minWidth: 0}}>
                      <span style={{fontSize: compact ? 18 : 14, color: isCurrent ? palette[2] : '#c1cadd'}}>{item.duration.toFixed(1)}s</span>
                      <div style={{width: '70%', maxWidth: 80, height: barHeight, borderRadius: '12px 12px 3px 3px', background: isCurrent ? palette[2] : `${palette[1]}`, border: `1px solid ${palette[2]}88`, boxShadow: isCurrent ? `0 0 28px ${palette[2]}66` : 'none'}} />
                      <span style={{width: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'center', fontSize: compact ? 16 : 12, color: isCurrent ? '#fff' : '#9daac0'}}>{item.scene_title}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={commonStyle}>
      <div style={{position: 'absolute', width: width * 0.72, height: width * 0.72, borderRadius: '50%', border: `1px solid ${palette[2]}55`, right: -width * 0.28, top: -width * 0.12, transform: `translateY(${drift}px)`}} />
      <div style={{position: 'absolute', width: width * 0.42, height: width * 0.42, borderRadius: '50%', background: `${palette[2]}18`, filter: 'blur(2px)', right: -width * 0.10, top: height * 0.28}} />
      {header}
      <div style={{fontSize: compact ? 27 : 23, opacity: 0.7, marginBottom: 18, letterSpacing: 1}}>{title}</div>
      <div style={{fontSize: compact ? 68 : 58, fontWeight: 800, lineHeight: 1.08, maxWidth: '92%', textWrap: 'balance' as const, textShadow: '0 8px 35px #0008'}}>
        {scene.scene_title}
      </div>
      <div style={{marginTop: compact ? 58 : 44, display: 'flex', flexDirection: 'column', gap: 18, maxWidth: '85%'}}>
        {points.slice(0, 3).map((point, pointIndex) => (
          <div key={pointIndex} style={{display: 'flex', gap: 16, alignItems: 'flex-start', fontSize: compact ? 31 : 26, lineHeight: 1.25, color: '#f4f5f7'}}>
            <span style={{color: palette[2], fontWeight: 800}}>✦</span><span>{point}</span>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Caption: React.FC<{sentence: Sentence; template: VideoProps['template']}> = ({sentence, template}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, 5], [0, 1], {extrapolateRight: 'clamp'});
  const fadeOut = interpolate(frame, [Math.max(0, (sentence.end - sentence.start) * fps - 5), (sentence.end - sentence.start) * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const compact = width < height;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', padding: compact ? '0 6% 7%' : '0 10% 6%', pointerEvents: 'none'}}>
      <div style={{
        opacity: Math.min(fadeIn, fadeOut),
        maxWidth: compact ? '94%' : '82%',
        padding: template === 'captions' ? (compact ? '24px 32px' : '18px 28px') : (compact ? '18px 26px' : '13px 22px'),
        borderRadius: template === 'captions' ? 28 : 18,
        background: template === 'captions' ? 'rgba(7, 12, 24, 0.9)' : 'rgba(3, 7, 18, 0.82)',
        border: '1px solid rgba(255,255,255,0.16)',
        color: '#fff',
        fontFamily: 'Arial, Helvetica, sans-serif',
        fontSize: template === 'captions' ? (compact ? 45 : 38) : (compact ? 37 : 30),
        fontWeight: template === 'captions' ? 800 : 700,
        lineHeight: template === 'captions' ? 1.2 : 1.28,
        textAlign: 'center',
        textShadow: '0 2px 8px #000',
        boxShadow: template === 'captions' ? '0 12px 50px #0008, 0 0 35px #ffffff18' : '0 10px 40px #0005',
      }}>{sentence.text}</div>
    </AbsoluteFill>
  );
};

const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const width = interpolate(frame, [0, durationInFrames], [0, 100], {extrapolateRight: 'clamp'});
  return <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 7, background: '#ffffff22'}}><div style={{height: '100%', width: `${width}%`, background: '#f6b73c'}} /></div>;
};

export const IdeaToVideo: React.FC<VideoProps> = (props) => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{background: '#080d19'}}>
      {props.scenes.map((scene, index) => (
        <Sequence key={`scene-${scene.id}`} from={Math.max(0, Math.round(scene.start * fps))} durationInFrames={Math.max(1, Math.ceil(scene.duration * fps))}>
          <SceneCard scene={scene} index={index} title={props.title} projectName={props.projectName} template={props.template} allScenes={props.scenes} />
        </Sequence>
      ))}
      {props.audioTracks.map((track, index) => (
        <Sequence key={`audio-${index}`} from={Math.max(0, Math.round(track.start * fps))} durationInFrames={Math.max(1, Math.ceil(track.duration * fps))}>
          <Audio src={staticFile(track.src)} volume={1} />
        </Sequence>
      ))}
      {props.sentences.map((sentence) => (
        <Sequence key={`sentence-${sentence.id}`} from={Math.max(0, Math.floor(sentence.start * fps))} durationInFrames={Math.max(1, Math.ceil((sentence.end - sentence.start) * fps))}>
          <Caption sentence={sentence} template={props.template} />
        </Sequence>
      ))}
      <ProgressBar />
    </AbsoluteFill>
  );
};
