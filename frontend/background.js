document.addEventListener("DOMContentLoaded", () => {
    const canvas = document.getElementById("bg-canvas");
    const ctx = canvas.getContext("2d");
    
    let width, height;
    let stars = [];
    let mouse = { x: undefined, y: undefined };
    
    const config = {
        starColor: "rgba(255, 255, 255, 0.5)",
        lineColor: "rgba(255, 255, 255, 0.3)",
        starWidth: 1.5,
        lineDistance: 120,
        velocity: 0.15,
        numStars: Math.floor(window.innerWidth / 8)
    };

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initStars();
    }

    function initStars() {
        stars = [];
        for (let i = 0; i < config.numStars; i++) {
            stars.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (config.velocity - Math.random() * 0.5),
                vy: (config.velocity - Math.random() * 0.5),
                radius: Math.random() * config.starWidth
            });
        }
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        
        ctx.fillStyle = config.starColor;
        ctx.strokeStyle = config.lineColor;
        ctx.lineWidth = 0.5;

        for (let i = 0; i < stars.length; i++) {
            let s = stars[i];
            s.x += s.vx;
            s.y += s.vy;

            if (s.x < 0 || s.x > width) s.vx = -s.vx;
            if (s.y < 0 || s.y > height) s.vy = -s.vy;

            ctx.beginPath();
            ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
            ctx.fill();

            // Lines to mouse
            if (mouse.x !== undefined) {
                let dx = s.x - mouse.x;
                let dy = s.y - mouse.y;
                let dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    ctx.beginPath();
                    ctx.moveTo(s.x, s.y);
                    ctx.lineTo(mouse.x, mouse.y);
                    ctx.stroke();
                }
            }

            // Lines between stars
            for (let j = i + 1; j < stars.length; j++) {
                let s2 = stars[j];
                let dx = s.x - s2.x;
                let dy = s.y - s2.y;
                let dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < config.lineDistance) {
                    ctx.beginPath();
                    ctx.moveTo(s.x, s.y);
                    ctx.lineTo(s2.x, s2.y);
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(animate);
    }

    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });
    window.addEventListener("mouseout", () => {
        mouse.x = undefined;
        mouse.y = undefined;
    });

    resize();
    animate();
});