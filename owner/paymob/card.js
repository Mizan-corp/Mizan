/*
 * Mizan card payment page (Paymob iframe): formatting, validation, the card
 * preview and the order summary. It never sends card data anywhere itself:
 * Paymob's own script submits #paymob_checkout with the [paymob_field] inputs.
 */
(function () {
  "use strict";

  var BRANDS = [
    { id: "amex", re: /^3[47]/, lengths: [15], cvv: 4, groups: [4, 6, 5] },
    { id: "meeza", re: /^(507803|507808|507809|507810|6000)/, lengths: [16, 19], cvv: 3, groups: [4, 4, 4, 4, 3] },
    { id: "mastercard", re: /^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))/, lengths: [16], cvv: 3, groups: [4, 4, 4, 4] },
    { id: "visa", re: /^4/, lengths: [13, 16, 19], cvv: 3, groups: [4, 4, 4, 4, 3] },
  ];
  var MARKS = {
    visa: '<span class="mz-mark-visa">VISA</span>',
    mastercard: '<span class="mz-mark-mc"></span>',
    meeza: '<span class="mz-mark-meeza">meeza</span>',
    amex: '<span class="mz-mark-amex">AMEX</span>',
  };

  function $(id) {
    return document.getElementById(id);
  }
  function digits(v) {
    return String(v || "").replace(/\D/g, "");
  }
  function brandOf(num) {
    for (var i = 0; i < BRANDS.length; i++) if (BRANDS[i].re.test(num)) return BRANDS[i];
    return null;
  }
  function luhn(num) {
    var sum = 0;
    for (var i = 0; i < num.length; i++) {
      var d = +num.charAt(num.length - 1 - i);
      if (i % 2) {
        d *= 2;
        if (d > 9) d -= 9;
      }
      sum += d;
    }
    return num.length > 11 && sum % 10 === 0;
  }
  function group(num, groups) {
    var out = [];
    var pos = 0;
    for (var i = 0; i < groups.length && pos < num.length; i++) {
      out.push(num.slice(pos, pos + groups[i]));
      pos += groups[i];
    }
    if (pos < num.length) out.push(num.slice(pos));
    return out.join(" ");
  }

  /* The payment key (in the URL) is base64(JWT): it carries the amount, the billing
     name, its expiry and the extras Mizan adds (description). Display only. */
  function readPaymentKey() {
    try {
      var token = new URLSearchParams(window.location.search).get("payment_token");
      if (!token) return null;
      var jwt = token.indexOf(".") > 0 ? token : atob(token.replace(/-/g, "+").replace(/_/g, "/"));
      var body = jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      while (body.length % 4) body += "=";
      var json = decodeURIComponent(
        atob(body)
          .split("")
          .map(function (c) {
            return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
          })
          .join(""),
      );
      return JSON.parse(json);
    } catch (e) {
      return null;
    }
  }

  function init() {
    var form = $("paymob_checkout");
    if (!form) return;
    var card = $("mz-card");
    var numIn = $("mz-number");
    var expIn = $("mz-expiry");
    var cvvIn = $("mz-cvv");
    var nameIn = $("mz-name");
    var pay = $("mz-pay");
    var touched = {};
    var expired = false;

    /* ── Order summary ─────────────────────────────── */
    var claims = readPaymentKey();
    var amountLabel = "";
    if (claims && claims.amount_cents != null) {
      var amount = (claims.amount_cents / 100).toLocaleString("en-US", {
        minimumFractionDigits: claims.amount_cents % 100 ? 2 : 0,
        maximumFractionDigits: 2,
      });
      var cur = claims.currency === "EGP" || !claims.currency ? "ج.م" : claims.currency;
      $("mz-amount").innerHTML = '<bdi dir="ltr">' + amount + "</bdi><small>" + cur + "</small>";
      amountLabel = amount + " " + cur;
      $("mz-paylabel").textContent = "ادفع " + amountLabel;
    }
    var extra = (claims && claims.extra) || {};
    if (extra.description) $("mz-desc").textContent = String(extra.description).slice(0, 80);
    var bd = (claims && claims.billing_data) || {};
    var holder = [bd.first_name, bd.last_name]
      .filter(function (x) {
        return x && x !== "NA";
      })
      .join(" ");
    if (holder && /^[A-Za-z .'-]+$/.test(holder)) {
      nameIn.value = holder.toUpperCase();
    }
    if (claims && claims.exp) {
      var timer = $("mz-timer");
      var out = $("mz-countdown");
      timer.hidden = false;
      var tick = function () {
        var left = Math.max(0, Math.round(claims.exp - Date.now() / 1000));
        var m = Math.floor(left / 60);
        var s = left % 60;
        out.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
        timer.classList.toggle("mz-late", left < 120);
        if (left === 0 && !expired) {
          expired = true;
          timer.innerHTML = "<span>انتهت صلاحية صفحة الدفع. ارجع إلى لوحة المالك وابدأ الدفع من جديد.</span>";
          update();
        }
      };
      tick();
      setInterval(tick, 1000);
    }

    /* ── Fields ────────────────────────────────────── */
    function setError(input, errId, msg) {
      var show = touched[input.id] && msg;
      $(errId).textContent = show ? msg : "";
      if (show) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
      input.classList.toggle("mz-valid", !msg && !!input.value);
    }

    function checkNumber() {
      var num = digits(numIn.value);
      var brand = brandOf(num);
      var max = brand ? Math.max.apply(null, brand.lengths) : 19;
      num = num.slice(0, max);
      numIn.value = group(num, brand ? brand.groups : [4, 4, 4, 4, 3]);
      $("pm-number").value = num;
      card.setAttribute("data-brand", brand ? brand.id : "");
      $("mz-brandmark").innerHTML = brand ? MARKS[brand.id] : "";
      $("mz-numicon").innerHTML = brand ? MARKS[brand.id] : "";
      var masked = (num + "################".slice(0, Math.max(0, 16 - num.length))).replace(/#/g, "•");
      $("mz-pnumber").textContent = group(masked, brand ? brand.groups : [4, 4, 4, 4, 3]);
      cvvIn.maxLength = brand ? brand.cvv : 4;
      cvvIn.placeholder = brand && brand.cvv === 4 ? "••••" : "•••";
      var msg = "";
      if (!num) msg = "اكتب رقم البطاقة";
      else if (brand && brand.lengths.indexOf(num.length) < 0 && num.length < max) msg = "رقم البطاقة غير مكتمل";
      else if (!luhn(num)) msg = "رقم البطاقة غير صحيح";
      setError(numIn, "mz-number-err", msg);
      return { ok: !msg, complete: brand ? brand.lengths.indexOf(num.length) >= 0 : num.length >= 16, brand: brand };
    }

    function checkExpiry() {
      var d = digits(expIn.value).slice(0, 4);
      if (d.length === 1 && +d > 1) d = "0" + d;
      expIn.value = d.length > 2 ? d.slice(0, 2) + " / " + d.slice(2) : d;
      var mm = d.slice(0, 2);
      var yy = d.slice(2, 4);
      $("pm-mm").value = mm;
      $("pm-yy").value = yy;
      $("mz-pexp").textContent = (mm || "MM") + "/" + (yy || "YY");
      var msg = "";
      if (d.length < 4) msg = "اكتب الشهر والسنة (MM / YY)";
      else if (+mm < 1 || +mm > 12) msg = "الشهر يجب أن يكون من 01 إلى 12";
      else {
        var now = new Date();
        var end = new Date(2000 + +yy, +mm, 1);
        if (end <= new Date(now.getFullYear(), now.getMonth(), 1)) msg = "البطاقة منتهية الصلاحية";
        else if (+yy > (now.getFullYear() % 100) + 20) msg = "سنة الانتهاء غير صحيحة";
      }
      setError(expIn, "mz-expiry-err", msg);
      return !msg;
    }

    function checkCvv(brand) {
      var need = brand ? brand.cvv : 3;
      cvvIn.value = digits(cvvIn.value).slice(0, 4);
      $("mz-pcvv").textContent = cvvIn.value ? cvvIn.value.replace(/./g, "•") : need === 4 ? "••••" : "•••";
      var msg = cvvIn.value.length === need || (!brand && cvvIn.value.length === 4) ? "" : "رمز الأمان " + need + " أرقام";
      setError(cvvIn, "mz-cvv-err", msg);
      return !msg;
    }

    function checkName() {
      var v = nameIn.value.replace(/\s+/g, " ").replace(/^\s/, "");
      if (v !== nameIn.value) nameIn.value = v;
      $("mz-pname").textContent = v.trim() || "YOUR NAME";
      var msg = "";
      if (v.trim().length < 2) msg = "اكتب الاسم كما هو مطبوع على البطاقة";
      else if (!/^[A-Za-z][A-Za-z .'-]*$/.test(v.trim())) msg = "بالحروف الإنجليزية كما على البطاقة";
      setError(nameIn, "mz-name-err", msg);
      return !msg;
    }

    function update() {
      var n = checkNumber();
      var ok = n.ok & checkExpiry() & checkCvv(n.brand) & checkName();
      pay.disabled = !ok || expired;
      return { valid: !!ok && !expired, number: n };
    }

    function touch(e) {
      touched[e.target.id] = true;
      update();
    }

    numIn.addEventListener("input", function () {
      var r = update();
      if (r.number.complete && r.number.ok) expIn.focus();
    });
    expIn.addEventListener("input", function () {
      if (update() && digits(expIn.value).length === 4) cvvIn.focus();
    });
    expIn.addEventListener("keydown", function (e) {
      if (e.key === "Backspace" && /\s\/\s$/.test(expIn.value)) {
        e.preventDefault();
        expIn.value = expIn.value.slice(0, 2);
        update();
      }
    });
    cvvIn.addEventListener("input", function () {
      var brand = brandOf(digits(numIn.value));
      update();
      if (cvvIn.value.length === (brand ? brand.cvv : 3) && !nameIn.value) nameIn.focus();
    });
    nameIn.addEventListener("input", function () {
      var pos = nameIn.selectionStart;
      nameIn.value = nameIn.value.toUpperCase();
      nameIn.setSelectionRange(pos, pos);
      update();
    });
    [numIn, expIn, cvvIn, nameIn].forEach(function (el) {
      el.addEventListener("blur", touch);
    });
    cvvIn.addEventListener("focus", function () {
      card.classList.add("mz-flipped");
    });
    cvvIn.addEventListener("blur", function () {
      card.classList.remove("mz-flipped");
    });

    /* Stop an invalid form before Paymob's handler sees it; show the busy state otherwise. */
    document.addEventListener(
      "submit",
      function (e) {
        if (e.target !== form) return;
        [numIn, expIn, cvvIn, nameIn].forEach(function (el) {
          touched[el.id] = true;
        });
        var r = update();
        if (!r.valid) {
          e.preventDefault();
          e.stopImmediatePropagation();
          var first = form.querySelector('[aria-invalid="true"]');
          if (first) first.focus();
          return;
        }
        pay.classList.add("mz-busy");
        pay.disabled = true;
        $("mz-paylabel").textContent = "جاري الدفع…";
        // If Paymob shows an error on this page instead of moving on, let the customer retry.
        setTimeout(function () {
          pay.classList.remove("mz-busy");
          $("mz-paylabel").textContent = amountLabel ? "ادفع " + amountLabel : "ادفع";
          update();
        }, 25000);
      },
      true,
    );

    update();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
