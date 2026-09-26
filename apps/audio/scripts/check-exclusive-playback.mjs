import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';
const code = ts.transpileModule(fs.readFileSync('src/exclusivePlayback.ts', 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS}
}).outputText;
class Media {
    paused = true;
    currentTime = 42;
    pause() { this.paused = true; }
}
const preview = new Media(), result = new Media();
const elements = [preview, result];
let listener;
const root = {
    querySelectorAll: () => elements,
    addEventListener: (type, callback, capture) => {assert.equal(type, 'play');assert.equal(capture, true);listener = callback;},
    removeEventListener: (type, callback, capture) => {assert.equal(callback, listener);assert.equal(capture, true);listener = null;}
};
const context = {exports: {}, HTMLMediaElement: Media, document: root};
vm.runInNewContext(code, context);
let pending = true;
const cleanup = context.exports.installExclusivePlayback(active => {if (active !== result) pending = false;});
function play(media) {media.paused = false;listener({target: media});}
play(result);play(preview);
assert.equal(result.paused, true);
assert.equal(preview.paused, false);
assert.equal(pending, false, 'Preview supersedes a pending result request');
assert.equal(result.currentTime, 42, 'Switching playback preserves position');
play(result);
assert.equal(preview.paused, true);
assert.equal(result.paused, false);
const secondPreview = new Media();elements.push(secondPreview);play(secondPreview);
assert.equal(result.paused, true);
assert.equal(secondPreview.paused, false);
context.exports.pauseOtherAudio(null);
assert.ok(elements.every(media => media.paused));
listener({target: {}});
cleanup();assert.equal(listener, null);
console.log('Exclusive playback passed: both directions, dynamically mounted previews, pending request cancellation, pause positions and cleanup.');
