/**
 * Khmer Latin Keyboard Switcher & Auto-Transliteration Engine
 * Automatically enables seamless English input and instant Khmer-to-Latin transliteration
 * for name fields without requiring manual OS keyboard switching (Alt+Shift).
 */

(function () {
    'use strict';

    // -------------------------------------------------------------------------
    // 1. Comprehensive Khmer NiDA Keyboard to English QWERTY Mapping
    // -------------------------------------------------------------------------
    const KHMER_NIDA_TO_EN = {
        // Consonants
        'ក': 'K', 'ខ': 'X', 'គ': 'K', 'ឃ': 'X', 'ង': 'G',
        'ច': 'C', 'ឆ': 'Q', 'ជ': 'C', 'ឈ': 'Q', 'ញ': 'J',
        'ដ': 'D', 'ឋ': 'D', 'ឌ': 'F', 'ឍ': 'F', 'ណ': 'N',
        'ត': 'T', 'ថ': 'T', 'ទ': 'V', 'ធ': 'V', 'ន': 'N',
        'ប': 'B', 'ផ': 'P', 'ព': 'P', 'ភ': 'B', 'ម': 'M',
        'យ': 'Y', 'រ': 'R', 'ល': 'L', 'វ': 'W', 'ស': 'S',
        'ហ': 'H', 'ឡ': 'L', 'អ': 'A',

        // Independent Vowels
        'ឥ': 'I', 'ឦ': 'I', 'ឧ': 'U', 'ឩ': 'U', 'ឪ': 'O',
        'ឫ': 'R', 'ឬ': 'R', 'ឭ': 'L', 'ឮ': 'L', 'ឯ': 'E',
        'ឰ': 'Y', 'ឱ': 'O', 'ឲ': 'O', 'ឳ': 'O',

        // Dependent Vowels
        'ា': 'A', 'ិ': 'I', 'ី': 'I', 'ឹ': 'W', 'ឺ': 'W',
        'ុ': 'U', 'ូ': 'U', 'ួ': 'Y', 'ើ': 'E', 'ឿ': 'E',
        'ៀ': 'I', 'េ': 'E', 'ែ': 'E', 'ៃ': 'Y', 'ោ': 'O',
        'ៅ': 'O', 'ុំ': 'M', 'ំ': 'M', 'ាំ': 'A', 'ះ': 'H',

        // Diacritics and signs
        'ៈ': ':', '៉': '', '៊': '', '់': '', '៌': '', '៍': '',
        '៎': '', '៏': '', '័': '', '៑': '', '្': '', '។': '.',
        '៕': '.', '៛': '$', 'ៗ': '',

        // Khmer Digits
        '០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4',
        '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'
    };

    // -------------------------------------------------------------------------
    // 2. Cambodian Names Transliteration Dictionary (Standard Official Spellings)
    // -------------------------------------------------------------------------
    const KHMER_NAME_DICT = {
        // Common Surnames & Given Names
        'សុភាព': 'SOPHEAP',
        'សុធីកា': 'SOTHYKA',
        'ស៊ឹម': 'SIM',
        'ស៊ីម': 'SIM',
        'ចាន់ថន': 'CHANTHORN',
        'មាស': 'MEAS',
        'វណ្ណា': 'VANNA',
        'កេង': 'KENG',
        'កុយ': 'KOY',
        'ដាវ': 'DAV',
        'ដាលីកា': 'DALYKA',
        'រ៉ាក់': 'RAK',
        'រាក់': 'RAK',
        'យ៉ាដានុត': 'YADANUTH',
        'សៀប': 'SIEB',
        'សេ': 'SE',
        'សុខ': 'SOK',
        'សៅ': 'SAO',
        'ហេង': 'HENG',
        'លី': 'LY',
        'ចាន់': 'CHAN',
        'ជា': 'CHEA',
        'គង់': 'KONG',
        'ឡុង': 'LONG',
        'ស្រី': 'SREY',
        'ម៉ៅ': 'MAO',
        'អ៊ុក': 'OUK',
        'សុភា': 'SOPHEA',
        'សុភ័ក្រ': 'SOPHEAK',
        'រ័ត្ន': 'ROTH',
        'រ័ត្នា': 'ROTHANA',
        'រតនា': 'ROTHANA',
        'សម្បត្តិ': 'SAMBATH',
        'វិបុល': 'VIBOL',
        'ធីតា': 'THIDA',
        'បូរី': 'BOREY',
        'ពិសិដ្ឋ': 'PISETH',
        'បញ្ញា': 'PANHA',
        'កុសល': 'KOSAL',
        'ភារម្យ': 'PHEAROM',
        'ចរិយា': 'CHORIYA',
        'ដារ៉ា': 'DARA',
        'តារា': 'DARA',
        'សុវណ្ណ': 'SOVANN',
        'សុវណ្ណារ៉ា': 'SOVANNARA',
        'មុន្នី': 'MONY',
        'មុនី': 'MONY',
        'ចំរើន': 'CHAMROEUN',
        'សេង': 'SENG',
        'តែង': 'TAENG',
        'សុខា': 'SOKHA',
        'សាន': 'SAN',
        'សូន': 'SOUN',
        'ថៃ': 'THAI',
        'ឈុន': 'CHHUN',
        'ហួន': 'HOUN',
        'ខៀវ': 'KHIEV',
        'ប្រាក់': 'PRAK',
        'សួស': 'SOUS',
        'ខឹម': 'KHEM',
        'ទូច': 'TOUCH',
        'ម៉ែន': 'MEN',
        'យី': 'YI',
        'ឈាង': 'CHHEANG',
        'សួន': 'SUON',
        'អ៊ឹម': 'IM',
        'អ៊ិន': 'IN',
        'អ៊ុំ': 'UM',
        'យន': 'YONN',
        'សូថា': 'SOTHA',
        'មី': 'MY',
        'កន': 'KONN',
        'គឹម': 'KIM',
        'កែវ': 'KEO',
        'សៀង': 'SIENG',
        'ហ៊ាង': 'HEANG',
        'ហ៊ួត': 'HUOT',
        'ឈិត': 'CHHIT',
        'ឡាយ': 'LAY',
        'ឡេង': 'LENG',
        'អ៊ាង': 'EANG',
        'អ៊ុច': 'OUCH',
        'ទិត្យ': 'TITH',
        'ទិត': 'TITH',
        'ទ្រី': 'TRY',
        'ពៅ': 'POV',
        'សាត': 'SAT',
        'សំ': 'SAM',
        'សំអុល': 'SAMOL',
        'សំអាន': 'SAMAN',
        'សុត': 'SOTH',
        'ស៊ុន': 'SUN',
        'សែម': 'SAEM',
        'ហាក់': 'HAK',
        'ហុង': 'HONG',
        'ឃឹម': 'KHIM',
        'ឃាង': 'KHEANG',
        'ខាត់': 'KHAT',
        'ស៊ន': 'SORN',
        'ម៉ន': 'MORN',
        'វ៉ែន': 'VAEN',
        'មុំ': 'MOM',
        'ម៉ុម': 'MOM',
        'នី': 'NY',
        'ដួង': 'DUONG',
        'ប៊ុន': 'BUN',
        'ព្រំ': 'PROM',
        'អែម': 'AEM',
        'រឿន': 'ROEUN',
        'លឿន': 'LOEUN',
        'សឿន': 'SOEUN',
        'ហ៊ាន': 'HEAN',
        'ហឿន': 'HOEUN',
        'ភឿន': 'PHOEUN',
        'ផាន់': 'PHAN',
        'ផាន': 'PHAN',
        'ប៉ុក': 'POK',
        'ប៉ែន': 'PAEN',
        'ប៉ាង': 'PANG',
        'សុក': 'SOK',
        'ម៉ុក': 'MOK',
        'ហោ': 'HOR',
        'ង៉ែត': 'NGET',
        'ង៉ោ': 'NGO',
        'សន': 'SORN',
        'ឈិន': 'CHHIN',
        'គីម': 'KIM',
        'សាយ': 'SAY',
        'សាន្ត': 'SAN',
        'ចិន': 'CHIN',
        'ផល': 'PHAL',
        'ផល្លា': 'PHALLA',
        'រ៉ា': 'RA',
        'រ៉ូ': 'RO',
        'ដា': 'DA',
        'លីន': 'LYN',
        'លីណា': 'LYNA',
        'ដាលីន': 'DALYN',
        'សុធី': 'SOTHY',
        'សុជាតា': 'SOCHEATA',
        'រដ្ឋា': 'ROTHA',
        'ចិន្តា': 'CHINDA',
        'សុខេង': 'SOKHENG',
        'រស្មី': 'REASMEY',
        'កល្យាណ': 'KALYAN',
        'មនោ': 'MANO',
        'សុជាតិ': 'SOCHEAT',
        'ចរណៃ': 'CHORNAY',
        'សុផាត': 'SOPHAT',
        'វិច្ឆិកា': 'VICHEKA',
        'វាសនា': 'VEASNA',
        'វីរៈ': 'VIRAK',
        'វុទ្ធី': 'VUTHY',
        'ណារិន': 'NARIN',
        'ណារី': 'NARY',
        'ណាត': 'NATH',
        'តាំង': 'TANG',
        'ថន': 'THORN',
        'ធារ៉ា': 'THEARA',
        'និមល': 'NIMOL',
        'និត': 'NITH',
        'នាង': 'NEANG',
        'នូ': 'NOU',
        'នេត្រ': 'NETR',
        'ប៊ុនណា': 'BUNNA',
        'ភា': 'PHEA',
        'ភី': 'PHY',
        'ភួង': 'PHUONG',
        'មាឃ': 'MEAKH',
        'ម៉េង': 'MENG',
        'ម៉ារ៉ា': 'MARA',
        'យ៉ាន': 'YAN',
        'រដ្ឋ': 'RATH',
        'លក្ខណ៍': 'LEAK',
        'លាង': 'LEANG',
        'លីដា': 'LYDA',
        'វិចិត្រ': 'VICHET',
        'វិទូ': 'VITOU',
        'វ៉ាន់': 'VAN',
        'ស៊ីណា': 'SYNA',
        'ស៊ីដា': 'SYDA',
        'ហង្ស': 'HANG',
        'អាន': 'AN',
        'អៀង': 'IENG',
        'អុល': 'OL',
        'អឿន': 'OEUN',
        'អៀម': 'IEAM',
        'ឃួន': 'KHUON',
        'ឈាន': 'CHHEAN',
        'ញ៉ែម': 'NHAEM',
        'ឈឹម': 'CHHIM',
        'ថាន': 'THAN',
        'ធឿន': 'THOEUN',
        'ប៊ន': 'BORN',
        'លាស់': 'LOAS',
        'ឡាត': 'LAT',
        'សុំ': 'SOM',
        'ម៉ែន': 'MEN'
    };

    // Phonetic rule components
    const KHMER_CONSONANTS = {
        'ក': 'K', 'ខ': 'KH', 'គ': 'K', 'ឃ': 'KH', 'ង': 'NG',
        'ច': 'CH', 'ឆ': 'CHH', 'ជ': 'CH', 'ឈ': 'CHH', 'ញ': 'NH',
        'ដ': 'D', 'ឋ': 'TH', 'ឌ': 'D', 'ឍ': 'TH', 'ណ': 'N',
        'ត': 'T', 'ថ': 'TH', 'ទ': 'T', 'ធ': 'TH', 'ន': 'N',
        'ប': 'B', 'ផ': 'PH', 'ព': 'P', 'ភ': 'PH', 'ម': 'M',
        'យ': 'Y', 'រ': 'R', 'ល': 'L', 'វ': 'V', 'ស': 'S',
        'ហ': 'H', 'ឡ': 'L', 'អ': 'A'
    };

    const KHMER_SUB_CONSONANTS = {
        '្ក': 'K', '្ខ': 'KH', '្គ': 'K', '្ឃ': 'KH', '្ង': 'NG',
        '្ច': 'CH', '្ឆ': 'CHH', '្ជ': 'CH', '្ឈ': 'CHH', '្ញ': 'NH',
        '្ដ': 'D', '្ឋ': 'TH', '្ឌ': 'D', '្ឍ': 'TH', '្ណ': 'N',
        '្ត': 'T', '្ថ': 'TH', '្ទ': 'T', '្ធ': 'TH', '្ន': 'N',
        '្ប': 'B', '្ផ': 'PH', '្ព': 'P', '្ភ': 'PH', '្ម': 'M',
        '្យ': 'Y', '្រ': 'R', '្ល': 'L', '្វ': 'V', '្ស': 'S',
        '្ហ': 'H', '្អ': 'A'
    };

    const KHMER_VOWELS = {
        'ា': 'A', 'ិ': 'I', 'ី': 'Y', 'ឹ': 'OE', 'ឺ': 'EU',
        'ុ': 'U', 'ូ': 'OU', 'ួ': 'UOR', 'ើ': 'ER', 'ឿ': 'OEU',
        'ៀ': 'IE', 'េ': 'E', 'ែ': 'AE', 'ៃ': 'AI', 'ោ': 'AO',
        'ៅ': 'OV', 'ុំ': 'OM', 'ំ': 'AM', 'ាំ': 'AM', 'ះ': 'AH',
        'ុះ': 'OH', 'េះ': 'EH', 'ោះ': 'AOH'
    };

    /**
     * Transliterate a single Khmer word to Latin
     */
    function transliterateKhmerWord(word) {
        if (!word) return '';
        const trimmed = word.trim();
        if (KHMER_NAME_DICT[trimmed]) {
            return KHMER_NAME_DICT[trimmed];
        }

        // Algorithmic romanization
        let result = '';
        let i = 0;
        const len = trimmed.length;

        while (i < len) {
            // Check subscript consonant (coeng + consonant)
            if (trimmed[i] === '្' && i + 1 < len) {
                const subKey = trimmed.substring(i, i + 2);
                if (KHMER_SUB_CONSONANTS[subKey]) {
                    result += KHMER_SUB_CONSONANTS[subKey];
                    i += 2;
                    continue;
                }
            }

            // Check compound vowels (e.g. ុះ, េះ, ោះ, ាំ)
            if (i + 1 < len) {
                const compoundVowel = trimmed.substring(i, i + 2);
                if (KHMER_VOWELS[compoundVowel]) {
                    result += KHMER_VOWELS[compoundVowel];
                    i += 2;
                    continue;
                }
            }

            const char = trimmed[i];

            if (KHMER_VOWELS[char]) {
                result += KHMER_VOWELS[char];
            } else if (KHMER_CONSONANTS[char]) {
                result += KHMER_CONSONANTS[char];
            } else if (KHMER_NIDA_TO_EN[char] !== undefined) {
                result += KHMER_NIDA_TO_EN[char];
            } else if (/[A-Za-z0-9\s\-]/.test(char)) {
                result += char.toUpperCase();
            }

            i++;
        }

        return result;
    }

    /**
     * Transliterate full Khmer name (e.g. 'សុភាព សុធីកា' -> 'SOPHEAP SOTHYKA')
     */
    function transliterateKhmerName(khmerName) {
        if (!khmerName || typeof khmerName !== 'string') return '';
        const words = khmerName.trim().split(/\s+/);
        return words.map(w => transliterateKhmerWord(w)).filter(Boolean).join(' ');
    }

    /**
     * Convert raw Khmer NiDA keystrokes / text directly to English uppercase
     */
    function convertKhmerKeystrokesToEnglish(str) {
        if (!str) return '';
        let out = '';
        for (let i = 0; i < str.length; i++) {
            const c = str[i];
            if (KHMER_NIDA_TO_EN[c] !== undefined) {
                out += KHMER_NIDA_TO_EN[c];
            } else if (/[a-zA-Z0-9\s\-]/.test(c)) {
                out += c.toUpperCase();
            }
        }
        return out.replace(/\s+/g, ' ');
    }

    // -------------------------------------------------------------------------
    // 3. UI Helper: Auto English Switcher & Transliteration Attachment
    // -------------------------------------------------------------------------

    // Track fields that have been auto-initialized
    const initializedInputs = new WeakSet();

    /**
     * Shows a subtle indicator showing English mode is active
     */
    function showEnglishActiveBadge(input) {
        let badge = document.getElementById('khLatinModeBadge');
        if (!badge) {
            badge = document.createElement('div');
            badge.id = 'khLatinModeBadge';
            badge.className = 'kh-latin-mode-badge';
            badge.innerHTML = `
                <div class="kh-badge-dot"></div>
                <span class="font-mono font-bold tracking-wider">🔤 ENGLISH / LATIN</span>
                <span class="kh-badge-desc">Auto-Locked</span>
            `;
            document.body.appendChild(badge);
        }

        const rect = input.getBoundingClientRect();
        badge.style.top = `${window.scrollY + rect.top - 28}px`;
        badge.style.left = `${window.scrollX + rect.right - 180}px`;
        badge.classList.add('active');

        clearTimeout(badge._hideTimeout);
        badge._hideTimeout = setTimeout(() => {
            badge.classList.remove('active');
        }, 2200);
    }

    function hideEnglishActiveBadge() {
        const badge = document.getElementById('khLatinModeBadge');
        if (badge) badge.classList.remove('active');
    }

    /**
     * Setup an input field for Latin / English lock & auto transliteration
     */
    function setupLatinInputField(input) {
        if (!input || initializedInputs.has(input)) return;
        initializedInputs.add(input);

        // Set modern input attributes
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('autocapitalize', 'characters');
        input.setAttribute('inputmode', 'text');
        input.setAttribute('lang', 'en');
        input.setAttribute('spellcheck', 'false');
        input.classList.add('kh-latin-auto-input');

        // Locate paired Khmer Name input in the same form or modal
        const form = input.closest('form') || input.closest('.modal-body') || input.closest('div.grid');
        let khmerInput = null;

        if (form) {
            khmerInput = form.querySelector('[name="name_kh"], #add_name_kh, #edit_name_kh, #editNameKh, #vgNameKh');
        }
        if (!khmerInput) {
            if (input.id === 'add_name_en') khmerInput = document.getElementById('add_name_kh');
            else if (input.id === 'edit_name_en') khmerInput = document.getElementById('edit_name_kh');
            else if (input.id === 'editNameEn') khmerInput = document.getElementById('editNameKh');
            else if (input.id === 'vgNameEn') khmerInput = document.getElementById('vgNameKh');
        }

        // Add 1-click Auto Transliterate button near the label if not already present
        const label = input.parentElement ? input.parentElement.querySelector('label') : null;
        if (label && !label.querySelector('.auto-transliterate-btn')) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'auto-transliterate-btn';
            btn.title = 'បម្លែងពីឈ្មោះខ្មែរទៅអក្សរឡាតាំងស្វ័យប្រវត្តិ (Auto-Transliterate)';
            btn.innerHTML = '⚡ បម្លែងស្វ័យប្រវត្តិ';
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (khmerInput && khmerInput.value.trim()) {
                    const latin = transliterateKhmerName(khmerInput.value);
                    if (latin) {
                        input.value = latin;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        if (window.showToast) {
                            showToast(`បម្លែងឈ្មោះជាអក្សរឡាតាំង៖ ${latin}`, 'success', 2500);
                        }
                    }
                } else {
                    input.focus();
                }
            });
            label.appendChild(btn);
        }

        // When Khmer input updates, sync to Latin input if Latin is empty or matching
        if (khmerInput && !khmerInput._hasLatinSync) {
            khmerInput._hasLatinSync = true;
            const syncHandler = () => {
                if (khmerInput.value.trim() && (!input.value.trim() || input._isAutoGenerated)) {
                    const generated = transliterateKhmerName(khmerInput.value);
                    if (generated) {
                        input.value = generated;
                        input._isAutoGenerated = true;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            };
            khmerInput.addEventListener('input', syncHandler);
            khmerInput.addEventListener('change', syncHandler);
            khmerInput.addEventListener('blur', syncHandler);
        }

        // When user focuses or clicks on Latin field
        input.addEventListener('focus', () => {
            showEnglishActiveBadge(input);
            // If empty and Khmer input has value, automatically transliterate
            if (!input.value.trim() && khmerInput && khmerInput.value.trim()) {
                const autoName = transliterateKhmerName(khmerInput.value);
                if (autoName) {
                    input.value = autoName;
                    input._isAutoGenerated = true;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.select();
                }
            }
        });

        input.addEventListener('blur', () => {
            hideEnglishActiveBadge();
            input.value = input.value.trim().toUpperCase();
        });

        // ---------------------------------------------------------------------
        // Intercept Keydown: Force English QWERTY Character output
        // Regardless of whether Windows is set to Khmer Unicode Keyboard!
        // ---------------------------------------------------------------------
        input.addEventListener('keydown', (e) => {
            // Allow control keys (Ctrl, Alt, Meta shortcuts, Tab, Enter, Backspace, Arrows)
            if (e.ctrlKey || e.altKey || e.metaKey) return;
            if (['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Tab', 'Enter', 'Escape', 'Home', 'End'].includes(e.key)) {
                return;
            }

            input._isAutoGenerated = false;

            // Physical key mapping (KeyA -> 'A', KeyB -> 'B', etc.)
            if (e.code && e.code.startsWith('Key')) {
                const letter = e.code.substring(3).toUpperCase();
                e.preventDefault();
                insertTextAtCursor(input, letter);
                showEnglishActiveBadge(input);
                return;
            }

            if (e.code === 'Space') {
                e.preventDefault();
                insertTextAtCursor(input, ' ');
                return;
            }

            if (e.code && e.code.startsWith('Digit')) {
                const digit = e.code.substring(5);
                e.preventDefault();
                insertTextAtCursor(input, digit);
                return;
            }

            if (e.code === 'Minus') {
                e.preventDefault();
                insertTextAtCursor(input, '-');
                return;
            }

            if (e.code === 'Slash') {
                e.preventDefault();
                insertTextAtCursor(input, '/');
                return;
            }

            if (e.code === 'Period') {
                e.preventDefault();
                insertTextAtCursor(input, '.');
                return;
            }
        });

        // Fallback for paste, mobile input, or composition
        input.addEventListener('input', () => {
            const original = input.value;
            // Check if contains Khmer Unicode characters
            if (/[\u1780-\u17FF]/.test(original)) {
                // If typed word-by-word or pasted, map or transliterate
                const converted = convertKhmerKeystrokesToEnglish(original);
                input.value = converted.toUpperCase();
            } else {
                input.value = original.toUpperCase();
            }
        });
    }

    /**
     * Helper to insert text at current cursor/selection position
     */
    function insertTextAtCursor(input, text) {
        const start = input.selectionStart || 0;
        const end = input.selectionEnd || 0;
        const val = input.value;

        input.value = val.substring(0, start) + text + val.substring(end);
        const newPos = start + text.length;
        input.setSelectionRange(newPos, newPos);
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // -------------------------------------------------------------------------
    // 4. Global Auto-Binding for all Latin / English Name Inputs
    // -------------------------------------------------------------------------
    function initAllLatinInputs() {
        const selectors = [
            'input[name="name_en"]',
            '#add_name_en',
            '#edit_name_en',
            '#editNameEn',
            '#vgNameEn',
            'input.uppercase',
            'input[data-latin-input]',
            'input[placeholder*="SIM CHANTHORN"]',
            'input[placeholder*="Romiet"]'
        ];

        document.querySelectorAll(selectors.join(', ')).forEach(el => {
            if (el.tagName === 'INPUT' && el.type === 'text') {
                setupLatinInputField(el);
            }
        });
    }

    // Auto initialize on DOM ready and Dynamic Modals/DOM changes
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllLatinInputs);
    } else {
        initAllLatinInputs();
    }

    // Observe DOM mutations to auto-bind in dynamically opened modals
    const observer = new MutationObserver(() => {
        initAllLatinInputs();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Expose helpers globally
    window.KhmerKeyboardHelper = {
        transliterateKhmerName,
        convertKhmerKeystrokesToEnglish,
        setupLatinInputField,
        initAllLatinInputs
    };

})();
