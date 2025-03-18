document.addEventListener("DOMContentLoaded", function() {
    // Playlist array
    const playlist = {
        home: '/static/music2.mp3',  // Played on welcome, index, and lobby
        game: '/static/music.mp3'    // Played during game and final scoreboard
    };
    let currentTrack = playlist.home;
    let audioElement = new Audio(currentTrack);
    audioElement.loop = true;

    // Sound effects
    const selectSound = new Audio('/static/select.mp3');
    const submitSound = new Audio('/static/submit.mp3');
    const correctSound = new Audio('/static/correct.mp3');
    const wrongSound = new Audio('/static/wrong.mp3');
    const roundEndSound = new Audio('/static/round_end.mp3');

    // DOM elements
    const musicControlBtn = document.getElementById("music-control-btn");
    const muteBtn = document.getElementById("mute-btn");

    // Load saved state from sessionStorage
    const savedState = {
        isPlaying: sessionStorage.getItem("musicIsPlaying") === "true",
        currentTime: parseFloat(sessionStorage.getItem("musicCurrentTime")) || 0,
        isMuted: sessionStorage.getItem("musicIsMuted") === "true",
    };

    // Apply saved state to all audio elements
    audioElement.currentTime = savedState.currentTime;
    audioElement.muted = savedState.isMuted;
    selectSound.muted = savedState.isMuted;
    submitSound.muted = savedState.isMuted;
    correctSound.muted = savedState.isMuted;
    wrongSound.muted = savedState.isMuted;
    roundEndSound.muted = savedState.isMuted;

    // Only play if not muted and was playing before
    if (!savedState.isMuted && savedState.isPlaying) {
        audioElement.play().catch(err => {
            console.log("Autoplay blocked:", err);
        });
    }

    // Toggle music player visibility
    if (musicControlBtn) {
        musicControlBtn.addEventListener("click", function() {
            const musicPlayer = document.getElementById("music-player");
            if (musicPlayer) musicPlayer.classList.toggle("active");
        });
    }

    // Mute/Unmute toggle for all audio
    if (muteBtn) {
        muteBtn.addEventListener("click", function() {
            const isMuted = !audioElement.muted; // Toggle state
            audioElement.muted = isMuted;
            selectSound.muted = isMuted;
            submitSound.muted = isMuted;
            correctSound.muted = isMuted;
            wrongSound.muted = isMuted;
            roundEndSound.muted = isMuted;
            sessionStorage.setItem("musicIsMuted", isMuted);
            muteBtn.textContent = isMuted ? '🔊' : '🔇';
            muteBtn.classList.toggle("btn-muted", isMuted);
        });
    }

    // Save state periodically
    audioElement.addEventListener("timeupdate", function() {
        sessionStorage.setItem("musicCurrentTime", audioElement.currentTime);
    });

    // Handle page unload
    window.addEventListener("beforeunload", function() {
        sessionStorage.setItem("musicIsPlaying", !audioElement.paused);
        sessionStorage.setItem("musicCurrentTime", audioElement.currentTime);
        sessionStorage.setItem("musicIsMuted", audioElement.muted);
    });

    // Switch track function
    function switchTrack(newTrack) {
        if (currentTrack !== newTrack) {
            const wasPlaying = !audioElement.paused;
            audioElement.pause();
            currentTrack = newTrack;
            audioElement.src = currentTrack;
            audioElement.currentTime = 0;
            audioElement.muted = savedState.isMuted;
            if (wasPlaying && !savedState.isMuted) {
                audioElement.play().catch(err => console.log("Switch playback blocked:", err));
            }
        }
    }

    // Expose functions
    window.switchToGameMusic = function() { switchTrack(playlist.game); };
    window.switchToHomeMusic = function() { switchTrack(playlist.home); };
    window.playSelectSound = function() { selectSound.play(); };
    window.playSubmitSound = function() { submitSound.play(); };
    window.playCorrectSound = function() { correctSound.play(); };
    window.playWrongSound = function() { wrongSound.play(); };
    window.playRoundEndSound = function() { roundEndSound.play(); };
    window.muteToggle = function() {
        const isMuted = !audioElement.muted;
        audioElement.muted = isMuted;
        selectSound.muted = isMuted;
        submitSound.muted = isMuted;
        correctSound.muted = isMuted;
        wrongSound.muted = isMuted;
        roundEndSound.muted = isMuted;
        sessionStorage.setItem("musicIsMuted", isMuted);
        muteBtn.textContent = isMuted ? '🔊' : '🔇';
        muteBtn.classList.toggle("btn-muted", isMuted);
    };
});