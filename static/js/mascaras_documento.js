/** Máscaras de CEP, telefone, CPF/CNPJ e RG para formulários do App O.S. */
(function (global) {
    "use strict";

    function soDigitos(valor, maxLen) {
        const d = String(valor || "").replace(/\D/g, "");
        return maxLen ? d.slice(0, maxLen) : d;
    }

    function formatarCep(valor) {
        const d = soDigitos(valor, 8);
        if (d.length <= 5) return d;
        return d.slice(0, 5) + "-" + d.slice(5);
    }

    function formatarTelefoneFixo(valor) {
        const d = soDigitos(valor, 10);
        if (!d) return "";
        if (d.length <= 2) return "(" + d;
        if (d.length <= 6) return "(" + d.slice(0, 2) + ") " + d.slice(2);
        return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    }

    function formatarCelular(valor) {
        const d = soDigitos(valor, 11);
        if (!d) return "";
        if (d.length <= 2) return "(" + d;
        if (d.length <= 7) return "(" + d.slice(0, 2) + ") " + d.slice(2);
        return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
    }

    function formatarTelefoneAuto(valor) {
        const d = soDigitos(valor, 11);
        if (d.length > 10) return formatarCelular(valor);
        return formatarTelefoneFixo(valor);
    }

    function formatarCpfCnpj(valor) {
        const d = soDigitos(valor, 14);
        if (!d) return "";
        if (d.length <= 11) {
            if (d.length <= 3) return d;
            if (d.length <= 6) return d.slice(0, 3) + "." + d.slice(3);
            if (d.length <= 9) return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
            return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
        }
        if (d.length <= 12) {
            return d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" + d.slice(8);
        }
        return (
            d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" +
            d.slice(8, 12) + "-" + d.slice(12)
        );
    }

    function formatarRg(valor) {
        const bruto = String(valor || "").toUpperCase().replace(/[^0-9X]/g, "").slice(0, 9);
        if (!bruto) return "";
        if (bruto.length <= 2) return bruto;
        if (bruto.length <= 5) return bruto.slice(0, 2) + "." + bruto.slice(2);
        if (bruto.length <= 8) return bruto.slice(0, 2) + "." + bruto.slice(2, 5) + "." + bruto.slice(5);
        return bruto.slice(0, 2) + "." + bruto.slice(2, 5) + "." + bruto.slice(5, 8) + "-" + bruto.slice(8);
    }

    function vincularMascara(el, formatar) {
        if (!el || typeof formatar !== "function") return;
        let ajustando = false;
        function aplicar() {
            if (ajustando) return;
            const atual = el.value;
            const novo = formatar(atual);
            if (novo === atual) return;
            ajustando = true;
            try {
                el.value = novo;
            } finally {
                ajustando = false;
            }
        }
        el.addEventListener("input", aplicar);
        el.addEventListener("blur", aplicar);
    }

    function vincularMascarasFormularioOs() {
        const mapa = [
            ["cliente_cep", formatarCep],
            ["cliente_telefone", formatarTelefoneFixo],
            ["cliente_celular", formatarCelular],
            ["cliente_cpf_cnpj", formatarCpfCnpj],
            ["cliente_rg", formatarRg],
            ["entrega_telefone", formatarTelefoneAuto],
        ];
        mapa.forEach(function (par) {
            const el = document.getElementById(par[0]);
            vincularMascara(el, par[1]);
        });
    }

    function aplicarMascarasCamposOs() {
        const mapa = [
            ["cliente_cep", formatarCep],
            ["cliente_telefone", formatarTelefoneFixo],
            ["cliente_celular", formatarCelular],
            ["cliente_cpf_cnpj", formatarCpfCnpj],
            ["cliente_rg", formatarRg],
            ["entrega_telefone", formatarTelefoneAuto],
        ];
        mapa.forEach(function (par) {
            const el = document.getElementById(par[0]);
            if (el) el.value = par[1](el.value || "");
        });
    }

    global.MascarasDocumento = {
        formatarCep: formatarCep,
        formatarTelefoneFixo: formatarTelefoneFixo,
        formatarCelular: formatarCelular,
        formatarTelefoneAuto: formatarTelefoneAuto,
        formatarCpfCnpj: formatarCpfCnpj,
        formatarRg: formatarRg,
        vincularMascarasFormularioOs: vincularMascarasFormularioOs,
        aplicarMascarasCamposOs: aplicarMascarasCamposOs,
    };
})(typeof window !== "undefined" ? window : globalThis);
