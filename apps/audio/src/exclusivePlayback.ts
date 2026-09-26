/** Keep reference previews and the result player mutually exclusive. */
export function pauseOtherAudio(active: HTMLMediaElement | null, root: Document = document) {
    root.querySelectorAll<HTMLMediaElement>('audio, video').forEach(media => {
        if (media !== active && !media.paused) media.pause();
    });
}

export function installExclusivePlayback(onPlay: (media: HTMLMediaElement) => void, root: Document = document) {
    const handlePlay = (event: Event) => {
        if (!(event.target instanceof HTMLMediaElement)) return;
        pauseOtherAudio(event.target, root);
        onPlay(event.target);
    };
    // Media play events do not bubble; capture also covers newly mounted players.
    root.addEventListener('play', handlePlay, true);
    return () => root.removeEventListener('play', handlePlay, true);
}
