(function () {
  "use strict";

  var STORAGE_KEY = "suppliers_report_records_v1";
  var records = [];

  var FILE_FIELDS = ["contractFile", "invoiceFile", "actFile", "vtcFile"];
  var TEXT_FIELDS = [
    "supplierName", "inn", "contact",
    "contractNumber", "contractDate",
    "invoiceNumber", "invoiceDate",
    "actNumber", "actDate",
    "vtcNumber", "vtcDate", "vtcValue",
    "amount", "paymentStatus", "paidAmount",
    "paymentDate", "penaltyAmount", "penaltyReason",
    "notes"
  ];

  // ---------- storage ----------

  function load() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      records = raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.error("Failed to load records", e);
      records = [];
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch (e) {
      console.error("Failed to save records", e);
      toast("Не удалось сохранить: превышен лимит хранилища браузера. Попробуйте прикреплять файлы меньшего размера.");
    }
  }

  function uid() {
    return "r_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
  }

  // ---------- helpers ----------

  function fmtMoney(n) {
    n = Number(n) || 0;
    return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 }) + " ₸";
  }

  function fmtDate(s) {
    if (!s) return "—";
    var d = new Date(s + "T00:00:00");
    if (isNaN(d.getTime())) return s;
    return d.toLocaleDateString("ru-RU");
  }

  function statusLabel(s) {
    if (s === "paid") return "Оплачено";
    if (s === "partial") return "Частично";
    return "Не оплачено";
  }

  function statusBadgeClass(s) {
    if (s === "paid") return "badge-paid";
    if (s === "partial") return "badge-partial";
    return "badge-unpaid";
  }

  function toast(msg) {
    var el = document.getElementById("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.hidden = true; }, 3200);
  }

  function fileToDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve({ name: file.name, type: file.type, size: file.size, data: reader.result }); };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function fileSizeLabel(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  // ---------- rendering ----------

  function currentFilters() {
    return {
      q: document.getElementById("searchBox").value.trim().toLowerCase(),
      status: document.getElementById("statusFilter").value,
      sort: document.getElementById("sortField").value
    };
  }

  function filteredSorted() {
    var f = currentFilters();
    var list = records.filter(function (r) {
      if (f.status && r.paymentStatus !== f.status) return false;
      if (f.q) {
        var hay = (r.inn || "").toLowerCase();
        if (hay.indexOf(f.q) === -1) return false;
      }
      return true;
    });
    list.sort(function (a, b) {
      var field = f.sort;
      var av = a[field], bv = b[field];
      if (field === "amount" || field === "penaltyAmount") {
        return (Number(bv) || 0) - (Number(av) || 0);
      }
      if (field === "contractDate" || field === "paymentDate") {
        return (bv || "").localeCompare(av || "");
      }
      return (av || "").localeCompare(bv || "", "ru");
    });
    return list;
  }

  function docSummary(number, date) {
    if (!number && !date) return "—";
    var parts = [];
    if (number) parts.push("№" + number);
    if (date) parts.push(fmtDate(date));
    return parts.join(", ");
  }

  function render() {
    var list = filteredSorted();
    var tbody = document.getElementById("tableBody");
    tbody.innerHTML = "";
    document.getElementById("emptyState").hidden = records.length !== 0;

    list.forEach(function (r) {
      var tr = document.createElement("tr");
      tr.dataset.id = r.id;

      var penaltyCell = Number(r.penaltyAmount) > 0
        ? '<span class="penalty-val">' + fmtMoney(r.penaltyAmount) + "</span>"
        : '<span class="penalty-zero">—</span>';

      tr.innerHTML =
        "<td class=\"wrap\"><strong>" + escapeHtml(r.supplierName || "—") + "</strong>" +
          (r.inn ? "<br><span style=\"color:var(--text-muted);font-size:.78rem\">БИН " + escapeHtml(r.inn) + "</span>" : "") +
        "</td>" +
        "<td>" + escapeHtml(docSummary(r.contractNumber, r.contractDate)) + "</td>" +
        "<td>" + escapeHtml(docSummary(r.invoiceNumber, r.invoiceDate)) + "</td>" +
        "<td>" + escapeHtml(docSummary(r.actNumber, r.actDate)) + "</td>" +
        "<td>" + escapeHtml(docSummary(r.vtcNumber, r.vtcDate)) + "</td>" +
        "<td>" + fmtMoney(r.amount) + "</td>" +
        "<td><span class=\"badge " + statusBadgeClass(r.paymentStatus) + "\">" + statusLabel(r.paymentStatus) + "</span>" +
          (r.paymentDate ? "<br><span style=\"color:var(--text-muted);font-size:.78rem\">" + fmtDate(r.paymentDate) + "</span>" : "") +
        "</td>" +
        "<td>" + penaltyCell + "</td>" +
        "<td><div class=\"row-actions\">" +
          "<button class=\"btn btn-sm btn-view\">Открыть</button>" +
          "<button class=\"btn btn-sm btn-edit\">Изм.</button>" +
          "<button class=\"btn btn-sm btn-danger btn-delete\">Удал.</button>" +
        "</div></td>";

      tbody.appendChild(tr);
    });

    renderSummary(list);
  }

  function renderSummary(list) {
    var totalAmount = 0, totalPaid = 0, totalPenalty = 0;
    list.forEach(function (r) {
      totalAmount += Number(r.amount) || 0;
      totalPaid += Number(r.paidAmount) || (r.paymentStatus === "paid" ? (Number(r.amount) || 0) : 0);
      totalPenalty += Number(r.penaltyAmount) || 0;
    });
    document.getElementById("sumCount").textContent = String(list.length);
    document.getElementById("sumAmount").textContent = fmtMoney(totalAmount);
    document.getElementById("sumPaid").textContent = fmtMoney(totalPaid);
    document.getElementById("sumDebt").textContent = fmtMoney(Math.max(totalAmount - totalPaid, 0));
    document.getElementById("sumPenalty").textContent = fmtMoney(totalPenalty);
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ---------- form ----------

  var form = document.getElementById("recordForm");
  var pendingFiles = {}; // fieldName -> {name,type,size,data} for the record being edited
  var removedFiles = {}; // fieldName -> true if user removed existing file

  function resetForm() {
    form.reset();
    document.getElementById("recordId").value = "";
    pendingFiles = {};
    removedFiles = {};
    FILE_FIELDS.forEach(function (f) {
      document.getElementById(f + "Preview").innerHTML = "";
    });
  }

  function openModal(title) {
    document.getElementById("modalTitle").textContent = title;
    document.getElementById("modalOverlay").hidden = false;
  }
  function closeModal() {
    document.getElementById("modalOverlay").hidden = true;
    resetForm();
  }

  function renderFilePreview(fieldName, existingFile) {
    var box = document.getElementById(fieldName + "Preview");
    box.innerHTML = "";
    var file = pendingFiles[fieldName] !== undefined ? pendingFiles[fieldName] : (removedFiles[fieldName] ? null : existingFile);
    if (!file) return;
    var chip = document.createElement("span");
    chip.className = "file-chip";
    var a = document.createElement("a");
    a.href = file.data;
    a.download = file.name;
    a.textContent = file.name + " (" + fileSizeLabel(file.size) + ")";
    chip.appendChild(a);
    var rm = document.createElement("button");
    rm.type = "button";
    rm.textContent = "✕";
    rm.title = "Убрать файл";
    rm.addEventListener("click", function () {
      pendingFiles[fieldName] = null;
      removedFiles[fieldName] = true;
      document.getElementById(fieldName).value = "";
      renderFilePreview(fieldName, null);
    });
    chip.appendChild(rm);
    box.appendChild(chip);
  }

  FILE_FIELDS.forEach(function (fieldName) {
    document.getElementById(fieldName).addEventListener("change", function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) {
        toast("Файл слишком большой (>8 МБ). Браузерное хранилище ограничено, выберите файл поменьше.");
        e.target.value = "";
        return;
      }
      fileToDataUrl(file).then(function (result) {
        pendingFiles[fieldName] = result;
        delete removedFiles[fieldName];
        renderFilePreview(fieldName, null);
      });
    });
  });

  function fillFormForEdit(r) {
    document.getElementById("recordId").value = r.id;
    TEXT_FIELDS.forEach(function (f) {
      var el = document.getElementById(f);
      if (el) el.value = r[f] !== undefined && r[f] !== null ? r[f] : "";
    });
    FILE_FIELDS.forEach(function (f) {
      renderFilePreview(f, r[f] || null);
    });
  }

  function readFormToRecord(existing) {
    var r = existing ? Object.assign({}, existing) : {
      id: uid(),
      createdAt: new Date().toISOString()
    };
    TEXT_FIELDS.forEach(function (f) {
      var el = document.getElementById(f);
      r[f] = el ? el.value : "";
    });
    FILE_FIELDS.forEach(function (f) {
      if (Object.prototype.hasOwnProperty.call(pendingFiles, f)) {
        r[f] = pendingFiles[f];
      } else if (removedFiles[f]) {
        r[f] = null;
      }
      // otherwise keep existing value untouched
    });
    r.updatedAt = new Date().toISOString();
    return r;
  }

  document.getElementById("btnAdd").addEventListener("click", function () {
    resetForm();
    openModal("Новая запись");
  });
  document.getElementById("btnCloseModal").addEventListener("click", closeModal);
  document.getElementById("btnCancel").addEventListener("click", closeModal);
  document.getElementById("modalOverlay").addEventListener("click", function (e) {
    if (e.target === this) closeModal();
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var id = document.getElementById("recordId").value;
    var existing = id ? records.find(function (x) { return x.id === id; }) : null;
    var rec = readFormToRecord(existing);
    if (existing) {
      records = records.map(function (x) { return x.id === id ? rec : x; });
      toast("Запись обновлена");
    } else {
      records.push(rec);
      toast("Запись добавлена");
    }
    persist();
    render();
    closeModal();
  });

  // ---------- view modal ----------

  function docViewSection(title, number, date, extra, file) {
    var items = "";
    items += viewItem("Номер", number || "—");
    items += viewItem("Дата", date ? fmtDate(date) : "—");
    if (extra) items += extra;
    var fileHtml = "";
    if (file) {
      fileHtml = "<div class=\"file-preview\"><span class=\"file-chip\"><a href=\"" + file.data + "\" download=\"" +
        escapeHtml(file.name) + "\">" + escapeHtml(file.name) + " (" + fileSizeLabel(file.size) + ")</a></span></div>";
    }
    return "<div class=\"view-section\"><h3>" + title + "</h3><div class=\"view-grid\">" + items + "</div>" + fileHtml + "</div>";
  }

  function viewItem(k, v) {
    return "<div class=\"view-item\"><div class=\"k\">" + k + "</div><div class=\"v\">" + escapeHtml(v) + "</div></div>";
  }

  function openView(r) {
    var body = document.getElementById("viewBody");
    var html = "";
    html += docViewSection("Поставщик", r.supplierName, null,
      viewItem("БИН", r.inn || "—") + viewItem("Контакт", r.contact || "—"), null);
    html += docViewSection("Договор", r.contractNumber, r.contractDate, null, r.contractFile);
    html += docViewSection("Накладная", r.invoiceNumber, r.invoiceDate, null, r.invoiceFile);
    html += docViewSection("Акт приёма-передачи", r.actNumber, r.actDate, null, r.actFile);
    html += docViewSection("Отчёт о внутритранспортной ценности", r.vtcNumber, r.vtcDate,
      viewItem("Ценность", r.vtcValue ? fmtMoney(r.vtcValue) : "—"), r.vtcFile);
    html += "<div class=\"view-section\"><h3>Оплата и пеня</h3><div class=\"view-grid\">" +
      viewItem("Сумма поставки", fmtMoney(r.amount)) +
      viewItem("Статус", statusLabel(r.paymentStatus)) +
      viewItem("Оплаченная сумма", fmtMoney(r.paidAmount)) +
      viewItem("Дата оплаты", r.paymentDate ? fmtDate(r.paymentDate) : "—") +
      viewItem("Пеня", fmtMoney(r.penaltyAmount)) +
      viewItem("Причина пени", r.penaltyReason || "—") +
      "</div></div>";
    if (r.notes) {
      html += "<div class=\"view-section\"><h3>Заметки</h3><div class=\"v\">" + escapeHtml(r.notes) + "</div></div>";
    }
    body.innerHTML = html;
    document.getElementById("viewOverlay").hidden = false;
  }

  document.getElementById("btnCloseView").addEventListener("click", function () {
    document.getElementById("viewOverlay").hidden = true;
  });
  document.getElementById("viewOverlay").addEventListener("click", function (e) {
    if (e.target === this) this.hidden = true;
  });

  // ---------- table events ----------

  document.getElementById("tableBody").addEventListener("click", function (e) {
    var tr = e.target.closest("tr");
    if (!tr) return;
    var id = tr.dataset.id;
    var r = records.find(function (x) { return x.id === id; });
    if (!r) return;

    if (e.target.classList.contains("btn-delete")) {
      if (confirm("Удалить запись по поставщику «" + (r.supplierName || "") + "»?")) {
        records = records.filter(function (x) { return x.id !== id; });
        persist();
        render();
        toast("Запись удалена");
      }
      return;
    }
    if (e.target.classList.contains("btn-edit")) {
      resetForm();
      fillFormForEdit(r);
      openModal("Редактирование записи");
      return;
    }
    // default / btn-view / row click
    openView(r);
  });

  // ---------- toolbar ----------

  document.getElementById("searchBox").addEventListener("input", render);
  document.getElementById("statusFilter").addEventListener("change", render);
  document.getElementById("sortField").addEventListener("change", render);

  // ---------- export / import ----------

  function downloadBlob(filename, content, mime) {
    var blob = new Blob([content], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  document.getElementById("btnExportJson").addEventListener("click", function () {
    downloadBlob("suppliers_" + new Date().toISOString().slice(0, 10) + ".json",
      JSON.stringify(records, null, 2), "application/json");
  });

  document.getElementById("btnExportCsv").addEventListener("click", function () {
    var cols = [
      "supplierName", "inn", "contact",
      "contractNumber", "contractDate",
      "invoiceNumber", "invoiceDate",
      "actNumber", "actDate",
      "vtcNumber", "vtcDate", "vtcValue",
      "amount", "paymentStatus", "paidAmount", "paymentDate",
      "penaltyAmount", "penaltyReason", "notes"
    ];
    var header = [
      "Поставщик", "БИН", "Контакт",
      "Номер договора", "Дата договора",
      "Номер накладной", "Дата накладной",
      "Номер акта", "Дата акта",
      "Номер отчёта ВТЦ", "Дата отчёта ВТЦ", "Ценность ВТЦ",
      "Сумма", "Статус оплаты", "Оплаченная сумма", "Дата оплаты",
      "Пеня", "Причина пени", "Заметки"
    ];
    var lines = [header.join(";")];
    records.forEach(function (r) {
      var row = cols.map(function (c) {
        var v = r[c] === undefined || r[c] === null ? "" : String(r[c]);
        v = v.replace(/"/g, '""');
        if (v.indexOf(";") !== -1 || v.indexOf("\n") !== -1 || v.indexOf('"') !== -1) v = '"' + v + '"';
        return v;
      });
      lines.push(row.join(";"));
    });
    downloadBlob("suppliers_" + new Date().toISOString().slice(0, 10) + ".csv",
      "﻿" + lines.join("\r\n"), "text/csv;charset=utf-8");
  });

  document.getElementById("importFile").addEventListener("change", function (e) {
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var data = JSON.parse(reader.result);
        if (!Array.isArray(data)) throw new Error("not an array");
        var merge = confirm(
          "Найдено " + data.length + " записей.\nOK — добавить к текущим, Отмена — заменить все текущие записи."
        );
        if (merge) {
          var existingIds = {};
          records.forEach(function (r) { existingIds[r.id] = true; });
          data.forEach(function (r) {
            if (!r.id || existingIds[r.id]) r.id = uid();
            records.push(r);
          });
        } else {
          records = data;
        }
        persist();
        render();
        toast("Импорт завершён");
      } catch (err) {
        toast("Ошибка импорта: файл повреждён или имеет неверный формат");
      }
      e.target.value = "";
    };
    reader.readAsText(file, "utf-8");
  });

  // ---------- init ----------

  load();
  render();
})();
