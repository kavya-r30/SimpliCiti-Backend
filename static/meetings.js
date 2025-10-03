let localStream;
let meetingId = null;

// Test meetings
const testMeetings = [
    {
        id: "test123",
        title: "Test Interview",
        participant: "Test Candidate",
        created_at: new Date().toISOString(),
        status: "scheduled"
    }
];

// Check if browser supports mediaDevices
function checkBrowserSupport() {
    if (!navigator.mediaDevices) {
        showNotification('❌ Your browser does not support camera access. Please use Chrome, Firefox, or Edge.', 'error');
        return false;
    }
    
    if (!navigator.mediaDevices.getUserMedia) {
        showNotification('❌ Camera access not supported in this browser.', 'error');
        return false;
    }
    
    return true;
}

async function createMeeting() {
    try {
        const response = await fetch('/api/meetings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: 'New Interview Meeting',
                participant: 'Candidate'
            })
        });
        
        const meeting = await response.json();
        meetingId = meeting.id;
        
        testMeetings.unshift(meeting);
        loadMeetings();
        showNotification('Meeting created! ID: ' + meetingId, 'success');
        
    } catch (error) {
        console.error('Error creating meeting:', error);
        showNotification('Error creating meeting', 'error');
    }
}

async function joinMeeting(id = null) {
    if (id) {
        meetingId = id;
    } else {
        meetingId = document.getElementById('meetingId').value.trim();
    }
    
    if (!meetingId) {
        showNotification('Please enter a meeting ID', 'error');
        return;
    }

    // Check browser support first
    if (!checkBrowserSupport()) {
        return;
    }

    try {
        await testCameraAccess();
        
    } catch (error) {
        console.error('Error joining meeting:', error);
        showNotification('Error: ' + error.message, 'error');
    }
}

async function testCameraAccess() {
    try {
        console.log('Requesting camera and microphone access...');
        
        // First try with simple constraints
        let constraints = { 
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 }
            },
            audio: true
        };
        
        localStream = await navigator.mediaDevices.getUserMedia(constraints);
        
        console.log('✅ Camera access granted!');
        displayLocalVideo();
        
    } catch (error) {
        console.error('Camera access failed:', error);
        
        // Try again without video constraints
        try {
            console.log('Trying without video constraints...');
            localStream = await navigator.mediaDevices.getUserMedia({ 
                video: true,
                audio: true 
            });
            
            console.log('✅ Camera access granted (fallback)!');
            displayLocalVideo();
            
        } catch (fallbackError) {
            console.error('Fallback also failed:', fallbackError);
            handleCameraError(fallbackError);
        }
    }
}

function displayLocalVideo() {
    const localVideo = document.getElementById('localVideo');
    
    // Set the stream
    localVideo.srcObject = localStream;
    
    // Play the video
    localVideo.play().then(() => {
        console.log('✅ Video is playing!');
        showNotification('🎥 Camera activated! You should see yourself now.', 'success');
        
        // Show video call UI
        document.getElementById('joinScreen').classList.add('hidden');
        document.getElementById('videoCall').classList.remove('hidden');
        document.getElementById('currentMeetingId').textContent = meetingId || 'test123';
        
        // Create simulated remote
        createSimulatedRemoteStream();
        
    }).catch(playError => {
        console.error('Error playing video:', playError);
        showNotification('⚠️ Camera is working but video display issue. Try refreshing.', 'info');
        
        // Still show the UI even if play fails
        document.getElementById('joinScreen').classList.add('hidden');
        document.getElementById('videoCall').classList.remove('hidden');
    });
}

function handleCameraError(error) {
    let errorMessage = 'Unknown camera error';
    
    switch(error.name) {
        case 'NotAllowedError':
            errorMessage = '❌ Camera access was denied. Please allow camera permissions and refresh the page.';
            break;
        case 'NotFoundError':
            errorMessage = '❌ No camera found on your device.';
            break;
        case 'NotSupportedError':
            errorMessage = '❌ Your browser does not support camera access.';
            break;
        case 'NotReadableError':
            errorMessage = '❌ Camera is already in use by another application.';
            break;
        case 'OverconstrainedError':
            errorMessage = '❌ Camera does not support the requested settings.';
            break;
        case 'SecurityError':
            errorMessage = '❌ Camera access is blocked for security reasons. Try using HTTPS.';
            break;
        default:
            errorMessage = `❌ Camera error: ${error.message}`;
    }
    
    showNotification(errorMessage, 'error');
    console.error('Camera error details:', error);
}

function createSimulatedRemoteStream() {
    const remoteVideo = document.getElementById('remoteVideo');
    
    remoteVideo.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-white p-4">
            <div class="text-center">
                <div class="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i class="fas fa-user text-2xl"></i>
                </div>
                <p class="text-lg font-semibold">Waiting for Candidate</p>
                <p class="text-sm text-gray-300 mt-2">Share this meeting ID:</p>
                <p class="text-xl font-mono font-bold text-yellow-300 mt-1">${meetingId || 'test123'}</p>
                <p class="text-xs text-gray-400 mt-4">Candidate will appear here when they join</p>
            </div>
        </div>
    `;
}

function toggleVideo() {
    if (localStream) {
        const videoTrack = localStream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = !videoTrack.enabled;
            const button = document.getElementById('videoToggle');
            button.classList.toggle('bg-red-600', !videoTrack.enabled);
            button.innerHTML = videoTrack.enabled ? 
                '<i class="fas fa-video"></i>' : 
                '<i class="fas fa-video-slash"></i>';
            
            showNotification(videoTrack.enabled ? '📹 Video ON' : '📹 Video OFF', 'info');
        }
    }
}

function toggleAudio() {
    if (localStream) {
        const audioTrack = localStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !audioTrack.enabled;
            const button = document.getElementById('audioToggle');
            button.classList.toggle('bg-red-600', !audioTrack.enabled);
            button.innerHTML = audioTrack.enabled ? 
                '<i class="fas fa-microphone"></i>' : 
                '<i class="fas fa-microphone-slash"></i>';
            
            showNotification(audioTrack.enabled ? '🎤 Audio ON' : '🎤 Audio OFF', 'info');
        }
    }
}

function leaveMeeting() {
    // Stop media tracks
    if (localStream) {
        localStream.getTracks().forEach(track => {
            track.stop();
            console.log('Stopped track:', track.kind);
        });
        localStream = null;
    }
    
    // Reset UI
    document.getElementById('joinScreen').classList.remove('hidden');
    document.getElementById('videoCall').classList.add('hidden');
    
    // Clear video elements
    const localVideo = document.getElementById('localVideo');
    localVideo.srcObject = null;
    
    meetingId = null;
    
    showNotification('👋 Left the meeting', 'info');
}

function loadMeetings() {
    const meetingList = document.getElementById('meetingList');
    
    meetingList.innerHTML = '';
    
    testMeetings.forEach(meeting => {
        const meetingElement = document.createElement('div');
        meetingElement.className = 'p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors';
        meetingElement.innerHTML = `
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <h4 class="font-semibold text-gray-900">${meeting.title}</h4>
                    <p class="text-sm text-gray-600">With: ${meeting.participant}</p>
                    <p class="text-xs text-gray-500">ID: ${meeting.id}</p>
                    <p class="text-xs text-green-600 font-semibold">Click to test camera</p>
                </div>
                <button onclick="event.stopPropagation(); joinMeeting('${meeting.id}')" 
                        class="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 ml-2">
                    <i class="fas fa-video"></i>
                </button>
            </div>
        `;
        
        meetingElement.addEventListener('click', () => joinMeeting(meeting.id));
        meetingList.appendChild(meetingElement);
    });
}

function showNotification(message, type = 'info') {
    const existingNotification = document.getElementById('notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    const notification = document.createElement('div');
    notification.id = 'notification';
    notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 max-w-md ${
        type === 'success' ? 'bg-green-500 text-white' :
        type === 'error' ? 'bg-red-500 text-white' :
        'bg-blue-500 text-white'
    }`;
    notification.innerHTML = `
        <div class="flex items-center">
            <span class="text-sm">${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Add browser check on load
function checkBrowserCompatibility() {
    const compatibilityInfo = document.getElementById('compatibilityInfo');
    
    if (!navigator.mediaDevices) {
        compatibilityInfo.innerHTML = `
            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                <strong>Browser Incompatible:</strong> Your browser does not support camera access. 
                Please use <strong>Google Chrome</strong> for the best experience.
            </div>
        `;
        return false;
    }
    
    compatibilityInfo.innerHTML = `
        <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
            <strong>Browser Compatible:</strong> Your browser supports video calling. 
            Make sure to <strong>allow camera and microphone access</strong> when prompted.
        </div>
    `;
    return true;
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadMeetings();
    checkBrowserCompatibility();
    console.log('Meeting system initialized');
    
    // Add browser info
    console.log('User Agent:', navigator.userAgent);
    console.log('Media Devices Support:', !!navigator.mediaDevices);
    console.log('GetUserMedia Support:', !!navigator.mediaDevices?.getUserMedia);
});