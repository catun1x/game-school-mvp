// Пасхальная падалка с куличами
(function() {
    let isRaining = false;
    let rainInterval = null;
    
    const KULICH_IMG_URL = 'https://s10.iimage.su/s/12/th_gHU8xUgxGAEazq88SRU1V7vSVeXp4svBXi2mgNzbz.png';
    
    function createFallingKulich() {
        const kulichContainer = document.createElement('div');
        kulichContainer.style.position = 'fixed';
        kulichContainer.style.left = Math.random() * window.innerWidth + 'px';
        kulichContainer.style.top = '-60px';
        kulichContainer.style.zIndex = '9999';
        kulichContainer.style.pointerEvents = 'none';
        
        const img = document.createElement('img');
        img.src = KULICH_IMG_URL;
        img.style.width = (35 + Math.random() * 20) + 'px';
        img.style.height = 'auto';
        img.style.display = 'block';
        img.style.filter = 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))';
        
        const rotation = -15 + Math.random() * 30;
        img.style.transform = `rotate(${rotation}deg)`;
        
        kulichContainer.appendChild(img);
        document.body.appendChild(kulichContainer);
        
        let pos = -60;
        const speed = 2 + Math.random() * 4;
        const rotationSpeed = (Math.random() - 0.5) * 2;
        let currentRotation = rotation;
        
        const fall = setInterval(() => {
            pos += speed;
            currentRotation += rotationSpeed;
            kulichContainer.style.top = pos + 'px';
            img.style.transform = `rotate(${currentRotation}deg)`;
            
            if (pos > window.innerHeight + 100) {
                clearInterval(fall);
                kulichContainer.remove();
            }
        }, 20);
    }
    
    function startRain() {
        if (rainInterval) return;
        isRaining = true;
        rainInterval = setInterval(() => {
            for(let i = 0; i < 4; i++) {
                createFallingKulich();
            }
        }, 120);
    }
    
    function stopRain() {
        if (rainInterval) {
            clearInterval(rainInterval);
            rainInterval = null;
        }
        isRaining = false;
    }
    
    function showMessage() {
        const msg = document.createElement('div');
        msg.innerHTML = '🐣 Христос Воскресе! 🐣';
        msg.style.position = 'fixed';
        msg.style.top = '50%';
        msg.style.left = '50%';
        msg.style.transform = 'translate(-50%, -50%)';
        msg.style.backgroundColor = 'rgba(0,0,0,0.92)';
        msg.style.color = '#ffd700';
        msg.style.fontSize = '34px';
        msg.style.fontWeight = 'bold';
        msg.style.padding = '35px 60px';
        msg.style.borderRadius = '25px';
        msg.style.zIndex = '10000';
        msg.style.textAlign = 'center';
        msg.style.border = '3px solid #ffd700';
        msg.style.boxShadow = '0 0 60px rgba(255,215,0,0.6)';
        msg.style.fontFamily = 'Segoe UI, Arial, sans-serif';
        msg.style.backdropFilter = 'blur(5px)';
        document.body.appendChild(msg);
        
        setTimeout(() => {
            msg.style.transition = 'opacity 0.5s, transform 0.5s';
            msg.style.opacity = '0';
            msg.style.transform = 'translate(-50%, -50%) scale(1.1)';
            setTimeout(() => msg.remove(), 500);
        }, 3500);
    }
    
    function initEasterEgg() {
        const btn = document.getElementById('easterEggBtn');
        if (!btn) return;
        
        btn.addEventListener('click', () => {
            if (!isRaining) {
                startRain();
                showMessage();
                setTimeout(() => {
                    stopRain();
                }, 8000);
            }
        });
    }
    
    // Ждём загрузки страницы
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEasterEgg);
    } else {
        initEasterEgg();
    }
})();