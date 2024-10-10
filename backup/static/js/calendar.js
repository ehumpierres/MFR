document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');
    var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        events: '/api/bookings/' + propertyId,
        eventClick: function(info) {
            showBookingDetails(info.event);
        },
        eventContent: function(arg) {
            let italicEl = document.createElement('i')
            if (arg.event.extendedProps.status === 'pending') {
                italicEl.innerHTML = 'PENDING - ' + arg.event.title
            } else {
                italicEl.innerHTML = arg.event.title
            }
            let arrayOfDomNodes = [ italicEl ]
            return { domNodes: arrayOfDomNodes }
        }
    });
    calendar.render();
});

function showBookingDetails(event) {
    var modal = document.getElementById('bookingModal');
    var modalTitle = document.getElementById('modalTitle');
    var modalBody = document.getElementById('modalBody');

    modalTitle.textContent = event.title;
    modalBody.innerHTML = `
        <p><strong>Start:</strong> ${event.start.toLocaleString()}</p>
        <p><strong>End:</strong> ${event.end.toLocaleString()}</p>
        <p><strong>Status:</strong> ${event.extendedProps.status}</p>
        <p><strong>Guest Name:</strong> ${event.extendedProps.guestName}</p>
        <p><strong>Guest Email:</strong> ${event.extendedProps.guestEmail}</p>
        <p><strong>Number of Guests:</strong> ${event.extendedProps.numGuests}</p>
        <p><strong>Catering Option:</strong> ${event.extendedProps.cateringOption}</p>
        <p><strong>Special Requests:</strong> ${event.extendedProps.specialRequests || 'None'}</p>
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
