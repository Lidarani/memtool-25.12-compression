# Copyright 2020-2023 NXP
"""TODO:summary line."""


def freq_find(target_freq):  # type: ignore
    """TODO:summary line."""
    f_osc = 24
    f_target = target_freq / 2
    threshold = 0

    m_max = 1023
    p_max = 63
    s_max = 7
    n_combinations = 0

    for s in range(0, s_max + 1):
        for p in range(1, p_max + 1):
            for m in range(1, m_max + 1):
                freq_found = (f_osc * m) / (p * 2 ** s)

                if abs(f_target - freq_found) <= threshold:
                    reg = m << 12 | p << 4 | s
                    n_combinations += 1
                    print(f'{target_freq} 0x{reg:x}, main=0x{m:x}, pre=0x{p:x}, post=0x{s:x}')
                    return 0

    return n_combinations


def freq_find_m850(target_freq):  # type: ignore
    """TODO:summary line."""
    f_osc = 25
    f_target = target_freq / 2
    threshold = 1

    DIVQ_max = 63
    DIVR1_max = 7
    DIVF1_max = 63
    DIVR2_max = 63
    DIVF2_max = 63
    n_combinations = 0

    for DIVQ in range(0, DIVQ_max+1):
        for DIVR1 in range(0, DIVR1_max+1):
            for DIVF1 in range(0, DIVF1_max+1):
                for DIVR2 in range(0, DIVR2_max+1):
                    for DIVF2 in range(0, DIVF2_max+1):
                        freq_found = f_osc / (DIVR1 + 1) * 2 * (DIVF1 + 1) / (DIVR2 + 1) * (DIVF2 + 1) / (DIVQ + 1)
                        if abs(f_target - freq_found) <= threshold:
                            reg = DIVR1 << 25 | DIVR2 << 19 | DIVF1 << 13 | DIVF2 << 7 | DIVQ << 1
                            n_combinations += 1
                            # if reg == 0x00ece580:
                            # print(f'{freq} 0x{reg:x} DIVR1 = {DIVR1} DIVR2 = {DIVR2}'
                            #          f' DIVF1 = {DIVF1} DIVF2 = {DIVF2} DIVQ = {DIVQ}')
                            print(f'\'{target_freq}\': \'0x{reg:x}\',')
                            return 0

    return n_combinations


if __name__ == "__main__":
    freq_list = [200, 267, 303, 333, 400, 533, 600, 625, 650, 667, 700, 733, 750, 800, 900, 933,
                 1000, 1050, 1066, 1100, 1200, 1300, 1450, 1500, 1600, 1800, 2000]

    print("PLL list")
    for freq in freq_list:
        n_combs = freq_find(freq)
        # TODO: do sth with freq_find return val

    print("PLL list 850")
    for frequency in freq_list:
        n_combs = freq_find_m850(frequency)
        # TODO: do sth with freq_find_m850 return val
