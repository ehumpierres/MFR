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
            alert('Booking: ' + info.event.title);
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
