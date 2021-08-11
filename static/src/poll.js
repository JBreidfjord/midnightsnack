$(function () {
  $("#poll").submit(function () {
    var rv = true;

    $('form#poll input[type="number"]').each(function () {
      var curr_invalid = false;
      var $current = $(this);

      if (!$current.val()) {
        curr_invalid = true;
        rv = false;
      } else {
        $('form#poll input[type="number"]').each(function () {
          if (
            $(this).val() == $current.val() &&
            $(this).attr("id") != $current.attr("id")
          ) {
            curr_invalid = true;
            rv = false;
          }
        });
      }

      if (curr_invalid) {
        $current.addClass("is-invalid");
      } else {
        $current.removeClass("is-invalid");
      }
    });

    if (rv) {
      return confirm(
        "Choices cannot be altered after submitting.\nAre you sure?"
      );
    }
    return false;
  });
});
