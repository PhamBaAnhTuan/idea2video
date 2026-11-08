import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const propsFile = process.argv[2];
const outputFile = process.argv[3];

if (!propsFile || !outputFile) {
  console.error('Usage: node render.mjs <input-props.json> <output.mp4>');
  process.exit(2);
}

const inputProps = JSON.parse(fs.readFileSync(propsFile, 'utf8'));
fs.mkdirSync(path.dirname(outputFile), {recursive: true});

console.log('[Remotion] Bundling composition...');
const serveUrl = await bundle({
  entryPoint: path.join(__dirname, 'src', 'index.ts'),
  publicDir: path.join(__dirname, 'public'),
  onProgress: (progress) => process.stdout.write(`\rBundle ${Math.round(progress * 100)}%`),
});
console.log('\n[Remotion] Selecting composition...');
const composition = await selectComposition({
  serveUrl,
  id: 'IdeaToVideo',
  inputProps,
});
console.log(`[Remotion] Rendering ${composition.width}x${composition.height}, ${composition.durationInFrames} frames...`);
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation: outputFile,
  inputProps,
  audioCodec: 'aac',
  pixelFormat: 'yuv420p',
  onProgress: ({progress}) => process.stdout.write(`\rRender ${Math.round(progress * 100)}%`),
});
console.log(`\n[Remotion] Saved: ${outputFile}`);
