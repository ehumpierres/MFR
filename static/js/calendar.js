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
        eventColor: '#378006',
        eventClick: function(info) {
            alert('Booking: ' + info.event.title);
        }
    });
    calendar.render();
});
