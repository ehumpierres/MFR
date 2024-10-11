document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');
    var isMobile = window.innerWidth < 768;

    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: isMobile ? 'listMonth' : 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: isMobile ? 'listMonth,dayGridMonth' : 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        views: {
            listMonth: {
                titleFormat: { year: 'numeric', month: 'long' }
            }
        },
        events: '/api/bookings/' + propertyId,
        eventClick: function(info) {
            showBookingDetails(info.event);
        },
        eventContent: function(arg) {
            if (isMobile && arg.view.type === 'listMonth') {
                return {
                    html: `<div class="fc-event-title">${arg.event.extendedProps.status === 'pending' ? 'PENDING - ' : ''}${arg.event.title}</div>`
                };
            } else {
                let italicEl = document.createElement('i');
                italicEl.innerHTML = arg.event.extendedProps.status === 'pending' ? 'PENDING - ' + arg.event.title : arg.event.title;
                return { domNodes: [italicEl] };
            }
        }
    });
    calendar.render();

    // Adjust calendar height for mobile
    function adjustCalendarHeight() {
        var fcViewContainer = document.querySelector('.fc-view-harness');
        if (fcViewContainer) {
            fcViewContainer.style.height = isMobile ? 'auto' : '600px';
        }
    }

    adjustCalendarHeight();
    window.addEventListener('resize', function() {
        isMobile = window.innerWidth < 768;
        calendar.changeView(isMobile ? 'listMonth' : 'dayGridMonth');
        adjustCalendarHeight();
    });
});

function showBookingDetails(event) {
    var modal = document.getElementById('bookingModal');
    var modalTitle = document.getElementById('modalTitle');
    var modalBody = document.getElementById('modalBody');

    modalTitle.textContent = event.title;
    modalBody.innerHTML = `
        <p><strong>Start Date:</strong> ${event.start.toLocaleDateString()}</p>
        <p><strong>End Date:</strong> ${event.end.toLocaleDateString()}</p>
        <p><strong>Arrival Time:</strong> ${event.extendedProps.arrivalTime}</p>
        <p><strong>Departure Time:</strong> ${event.extendedProps.departureTime}</p>
        <p><strong>Guest Name:</strong> ${event.extendedProps.guestName}</p>
        <p><strong>Guest Email:</strong> ${event.extendedProps.guestEmail}</p>
        <p><strong>Number of Guests:</strong> ${event.extendedProps.numGuests}</p>
        <p><strong>Catering Option:</strong> ${event.extendedProps.cateringOption}</p>
        <p><strong>Special Requests:</strong> ${event.extendedProps.specialRequests || 'None'}</p>
        <p><strong>Mobility Impaired:</strong> ${event.extendedProps.mobilityImpaired}</p>
        <p><strong>Event Manager Contact:</strong> ${event.extendedProps.eventManagerContact}</p>
        <p><strong>Offsite Emergency Contact:</strong> ${event.extendedProps.offsiteEmergencyContact}</p>
        <p><strong>Mitchell Sponsor:</strong> ${event.extendedProps.mitchellSponsor}</p>
        <p><strong>Type of Use:</strong> ${event.extendedProps.exclusiveUse}</p>
        <p><strong>Organization Type:</strong> ${event.extendedProps.organizationStatus}</p>
        <p><strong>Status:</strong> ${event.extendedProps.status}</p>
    `;

    modal.style.display = 'block';
}

// Close the modal when clicking on <span> (x)
document.querySelector('.close').onclick = function() {
    document.getElementById('bookingModal').style.display = 'none';
}

// Close the modal when clicking outside of it
window.onclick = function(event) {
    var modal = document.getElementById('bookingModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

