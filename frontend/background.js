(function() {    
    var camera, scene, renderer,
        container, stats, particle,
        winHalfX, winHalfY,
        height, width, fieldOfView,
        aspectRatio, nearPlane, farPlane,
        body, cameraZ, material,
        i = 0,
        count = 0,
        Tau = Math.PI * 2,
        mouseX = 0,
        mouseY = 0,
        amtX = 50,
        amtY = 50,
        sep = 100,
        particles = [];

    function onDocumentReady() {
        body = document.body;

        container = document.createElement('div');
        container.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none;';
        body.appendChild(container);

        height = window.innerHeight;
        winHalfY = height / 2;
        width = window.innerWidth;
        winHalfX = width / 2;
        fieldOfView = 75;
        aspectRatio = width / height;
        nearPlane = 1;
        farPlane = 10000;
        cameraZ = 750;

        document.addEventListener('mousemove', onDocumentMouseMove);
        document.addEventListener('touchstart', onDocumentTouchStart);
        document.addEventListener('touchmove', onDocumentTouchMove);
        window.addEventListener('resize', onWindowResize);
    
        // FIX: Only run if THREE exists (in case CDN fails)
        if (typeof THREE !== 'undefined') {
            rendererer(onRendererRenderered);
        }
    }

    function rendererer(complete) {
        camera = new THREE.PerspectiveCamera(fieldOfView, aspectRatio, nearPlane, farPlane);
        camera.position.z = cameraZ;

        scene = new THREE.Scene();

        var spriteCanvas = document.createElement('canvas');
        spriteCanvas.width = 32;
        spriteCanvas.height = 32;
        var spriteCtx = spriteCanvas.getContext('2d');
        spriteCtx.beginPath();
        spriteCtx.arc(16, 16, 16, 0, Tau, true);
        spriteCtx.fillStyle = '#ffffff';
        spriteCtx.fill();
        var spriteTexture = new THREE.CanvasTexture(spriteCanvas);

        material = new THREE.SpriteMaterial({ map: spriteTexture, transparent: true, color: 0xffffff });

        for (var ix = 0, lx = amtX; ix < lx; ix++) {
            for (var iy = 0, ly = amtY; iy < ly; iy++) {
                particle = particles[i++] = new THREE.Sprite(material);
                particle.position.x = ix * sep - ((amtX * sep) / 2);
                particle.position.z = iy * sep - ((amtY * sep) / 2);
                scene.add(particle);
            }
        }

        renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setClearColor(0x050810, 1); // Space black background
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(width, height);

        container.appendChild(renderer.domElement);
        
        if (complete) {
            complete();
        }
    }

    function onRendererRenderered() {
        // FIX: Only initialize Stats if the library actually loaded from the CDN
        if (typeof Stats !== 'undefined') {
            stats = new Stats();
            stats.domElement.style.position = 'absolute';
            stats.domElement.style.top = stats.domElement.style.right = '0';
            stats.domElement.style.display = 'none'; // Keep hidden for production
            container.appendChild(stats.domElement);
        }
    }

    function onDocumentMouseMove(e) {
        mouseX = e.clientX - winHalfX;
        mouseY = e.clientY - winHalfY;
    }

    function onDocumentTouchStart(e) {
        if (e.touches.length === 1) {
            e.preventDefault();
            mouseX = e.touches[0].pageX - winHalfX;
            mouseY = e.touches[0].pageY - winHalfY;
        }
    }

    function onDocumentTouchMove(e) {
        if (e.touches.length === 1) {
            e.preventDefault();
            mouseX = e.touches[0].pageX - winHalfX;
            mouseY = e.touches[0].pageY - winHalfY;
        }
    }

    function onWindowResize() {
        height = window.innerHeight;
        winHalfY = height / 2;
        width = window.innerWidth;
        winHalfX = width / 2;

        if (camera && renderer) {
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
            renderer.setSize(width, height);
        }
    }

    function animate() {
        requestAnimationFrame(animate);
        
        // FIX: If the 3D renderer or scene failed to build, don't crash the thread
        if (!renderer || !scene) return;
        
        update();
        
        // FIX: Only update stats if it was successfully initialized
        if (stats) {
            stats.update();
        }
    }

    function update() {
        camera.position.x += (mouseX - camera.position.x) * 0.05;
        camera.position.y += (-mouseY - camera.position.y) * 0.05;
        camera.lookAt(scene.position);
        
        i = 0;
        for (var ix = 0, lx = amtX; ix < lx; ix++) {
            for (var iy = 0, ly = amtY; iy < ly; iy++) {
                particle = particles[i++];
                particle.position.y = (Math.sin((ix + count) * 0.3) * 50) + (Math.sin((iy + count) * 0.5) * 50);
                particle.scale.x = particle.scale.y = (Math.sin((ix + count) * 0.3) + 1) * 4 + (Math.sin((iy + count) * 0.5) + 1) * 4;
            }
        }

        renderer.render(scene, camera);
        count += 0.1;
    }

    document.addEventListener('DOMContentLoaded', onDocumentReady);
    document.addEventListener('DOMContentLoaded', animate);

})();