document.addEventListener('DOMContentLoaded', function() {
    // Make active navigation item highlight
    const links = document.querySelectorAll('.list-group-item-action');
    
    if (links && links.length > 0) {
        // Smooth scrolling for anchor links
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetId = this.getAttribute('href');
                const targetElement = document.querySelector(targetId);
                
                if (targetElement) {
                    window.scrollTo({
                        top: targetElement.offsetTop - 20,
                        behavior: 'smooth'
                    });
                    
                    // Update active class
                    links.forEach(l => l.classList.remove('active'));
                    this.classList.add('active');
                }
            });
        });
        
        // Handle scroll events to update active section
        window.addEventListener('scroll', function() {
            const sections = document.querySelectorAll('section');
            let currentSection = null;
            
            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                const sectionHeight = section.clientHeight;
                
                if (window.pageYOffset >= sectionTop - 100 && 
                    window.pageYOffset < sectionTop + sectionHeight - 100) {
                    currentSection = section.id;
                }
            });
            
            if (currentSection) {
                links.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === `#${currentSection}`) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }
});