document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded event fired');
    var calendarEl = document.getElementById('calendar');
    console.log('Calendar element:', calendarEl);
    // ... rest of your calendar initialization code
  
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
                titleFormat: { year: 'numeric', month: 'long' },
                eventTimeFormat: {
                    hour: 'numeric',
                    minute: '2-digit',
                    meridiem: 'short'
                }
            }
        },
        events: '/api/bookings/' + propertyId,
        eventClick: function(info) {
            showBookingDetails(info.event);
        },
        eventContent: function(arg) {
            if (isMobile && arg.view.type === 'listMonth') {
                return {
                    html: `
                        <div class="fc-event-main-frame">
                            <div class="fc-event-title-container">
                                <div class="fc-event-title fc-sticky">
                                    ${arg.event.extendedProps.status === 'pending' ? '<span class="pending-tag">PENDING</span> ' : ''}
                                    ${arg.event.title}
                                </div>
                            </div>
                        </div>
                    `
                };
            } else {
                let italicEl = document.createElement('i');
                italicEl.innerHTML = arg.event.extendedProps.status === 'pending' ? 'PENDING - ' + arg.event.title : arg.event.title;
                return { domNodes: [italicEl] };
            }
        },
        longPressDelay: 100,
        eventLongPressDelay: 100,
        selectLongPressDelay: 100,
    });
    calendar.render();

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
        adjustModalForMobile();
    });
});

function showBookingDetails(event) {
    var modal = document.getElementById('bookingModal');
    var modalTitle = document.getElementById('modalTitle');
    var modalBody = document.getElementById('modalBody');

    modalTitle.textContent = event.title;

    if (window.innerWidth < 768) {
        modalBody.innerHTML = `
            <p><strong>Dates:</strong> ${event.start.toLocaleDateString()} - ${event.end.toLocaleDateString()}</p>
            <p><strong>Times:</strong> ${event.extendedProps.arrivalTime} - ${event.extendedProps.departureTime}</p>
            <p><strong>Guest:</strong> ${event.extendedProps.guestName}</p>
            <p><strong>Guests:</strong> ${event.extendedProps.numGuests}</p>
            <p><strong>Status:</strong> ${event.extendedProps.status}</p>
            <button onclick="showFullDetails(${JSON.stringify(event.extendedProps)})">Show Full Details</button>
        `;
    } else {
        showFullDetails(event.extendedProps);
    }

    modal.style.display = 'block';
}

function showFullDetails(eventProps) {
    var modalBody = document.getElementById('modalBody');
    modalBody.innerHTML = `
        <p><strong>Start Date:</strong> ${eventProps.start.toLocaleDateString()}</p>
        <p><strong>End Date:</strong> ${eventProps.end.toLocaleDateString()}</p>
        <p><strong>Arrival Time:</strong> ${eventProps.arrivalTime}</p>
        <p><strong>Departure Time:</strong> ${eventProps.departureTime}</p>
        <p><strong>Guest Name:</strong> ${eventProps.guestName}</p>
        <p><strong>Guest Email:</strong> ${eventProps.guestEmail}</p>
        <p><strong>Number of Guests:</strong> ${eventProps.numGuests}</p>
        <p><strong>Catering Option:</strong> ${eventProps.cateringOption}</p>
        <p><strong>Special Requests:</strong> ${eventProps.specialRequests || 'None'}</p>
        <p><strong>Mobility Impaired:</strong> ${eventProps.mobilityImpaired}</p>
        <p><strong>Event Manager Contact:</strong> ${eventProps.eventManagerContact}</p>
        <p><strong>Offsite Emergency Contact:</strong> ${eventProps.offsiteEmergencyContact}</p>
        <p><strong>Mitchell Sponsor:</strong> ${eventProps.mitchellSponsor}</p>
        <p><strong>Type of Use:</strong> ${eventProps.exclusiveUse}</p>
        <p><strong>Organization Type:</strong> ${eventProps.organizationStatus}</p>
        <p><strong>Status:</strong> ${eventProps.status}</p>
    `;
}

function adjustModalForMobile() {
    var modal = document.getElementById('bookingModal');
    var modalContent = modal.querySelector('.modal-content');
    if (window.innerWidth < 768) {
        modalContent.style.width = '95%';
        modalContent.style.margin = '5% auto';
    } else {
        modalContent.style.width = '80%';
        modalContent.style.margin = '10% auto';
    }
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

// Initial call to adjust modal for current screen size
adjustModalForMobile();


