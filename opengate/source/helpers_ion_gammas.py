import opengate as gate
import radioactivedecay as rd
import opengate_core as g4
from box import Box
import pathlib
import numpy as np


def define_ion_gamma_sources(source_type, name):
    print("define sources ", name)

    # create base user_info from a "fake" GS or VS (or GANS ?)
    ui = gate.UserInfo("Source", source_type, name)

    # some default param
    ui.energy.type = "ion_gamma"

    # add new parameters with default : ion, options etc
    return ui


def get_nuclide_progeny_az(z, a):
    a = int(a)
    z = int(z)
    id = int(f"{z:3}{a:3}0000")
    nuclide = rd.Nuclide(id)
    return get_all_nuclide_progeny(nuclide)


def get_nuclide_name_and_direct_progeny(z, a):
    a = int(a)
    z = int(z)
    id = int(f"{z:3}{a:3}0000")
    nuclide = rd.Nuclide(id)
    p = nuclide.progeny()
    return nuclide.nuclide, p


def get_all_nuclide_progeny(nuclide):
    # recurse until stable
    if nuclide.half_life() == "stable":
        return []
    # start a list of daughters
    p = []
    daugthers = nuclide.progeny()
    for d in daugthers:
        p.append(d)
        nuc_d = rd.Nuclide(d)
        p = p + get_all_nuclide_progeny(nuc_d)
    # remove duplicate
    p = list(set(p))
    return p


def get_ion_gamma_channels(ion, options={}):
    a = ion.a
    z = ion.z
    print(z, a)

    # FIXME
    w = [0.3, 0.3, 0.4]
    ene = [0.200, 0.300, 0.400]

    # get all channels and gammas for this ion
    g = gate.IonGammaExtractor(a, z)
    g.extract()
    gammas = g.gammas
    print(f"extracted {len(gammas)}")

    # create the final arrays of energy and weights
    energies = [g.energy for g in gammas]
    weights = [g.weight for g in gammas]
    return energies, weights


def get_ion_decays(a, z):
    print("tests")


"""
    # read file as a box, with gamma lines as box
    level_gamma = read_level_gamma(a, z)

    # parse the levels to get all energies
    weights = []
    energies = []
    for level in level_gamma:
        add_weights_and_energy_level(level_gamma, level, weights, energies)

    return w, ene
"""


def add_weights_and_energy_level_OLD(level_gamma, level, weights, energies):
    g = level_gamma[level]
    total_intensity = 0
    total_br = 0
    for d in g.daugthers.values():
        total_intensity += d.intensity
        d.br = (1 + d.alpha) * d.intensity
        total_br += d.br
    # print(f'total', total_intensity)
    """
    6) Total internal conversion coefficient : alpha = Ic/Ig
   Note1: total transition is the sum of gamma de-excitation and internal
          conversion. Therefore total branching ratio is proportional to
          (1+alpha)*Ig
   Note2: total branching ratios from a given level do not always sum up to
          100%. They are re-normalized internally.
   Note3: relative probabilities for gamma de-excitation and internal conversion
          are 1/(1+alpha) and alpha/(1+alpha) respectively
    """
    for d in g.daugthers.values():
        if total_br != 0:
            d.br = d.br / total_br
            print(
                f"{level} {d.daughter_order} br ={d.br}   (ig ={d.intensity} alpha={d.alpha})"
            )


def read_level_gamma(a, z, ignore_zero_deex=True):
    # get folder
    data_paths = g4.get_G4_data_paths()
    folder = pathlib.Path(data_paths["G4LEVELGAMMADATA"])
    ion_filename = folder / f"z{z}.a{a}"
    with open(ion_filename) as file:
        lines = [line for line in file]
    levels = Box()
    i = 0
    keV = gate.g4_units("keV")
    while i < len(lines) - 1:
        l = Box()
        words = lines[i].split()
        # 1)An integer defining the order index of the level starting by 0  for the ground state
        l.order_level = words[0]
        # 2)A string  defining floating level  (-,+X,+Y,+Z,+U,+V,+W,+R,+S,+T,+A,+B,+C)
        l.floating_level = words[1]
        # 3) Excitation energy of the level (keV)
        l.excitation_energy = float(words[2]) * keV
        # 4) Level half-life (s). A -1 half-life means a stable ground state.
        l.half_life = words[3]
        # 5) JPi information of the level.
        # 6) n_gammas= Number of possible gammas deexcitation channel from the level.
        l.n_gammas = int(words[5])
        # if no channel, we (may) ignore
        if ignore_zero_deex and l.n_gammas == 0:
            i += 1
            continue
        l.daugthers = Box()
        i += 1
        for j in range(0, l.n_gammas):
            a = read_one_gamma_deex_channel(lines[i])
            l.daugthers[a.daughter_order] = a
            i += 1
        levels[l.order_level] = l
    return levels


def read_one_gamma_deex_channel(line):
    keV = gate.g4_units("keV")
    words = line.split()
    l = Box()
    # 1) The order number of the daughter level.
    l.daughter_order = int(words[0])
    # 2) The energy of the gamma transition.
    l.transition_energy = float(words[1]) * keV
    # 3) The relative gamma emission intensity.
    l.intensity = float(words[2])
    """
    4)The multipolarity number with 1,2,3,4,5,6,7 representing E0,E1,M1,E2,M2,E3,M3  monopole transition
       and  100*Nx+Ny representing multipolarity transition with Ny and Ny taking the value 1,2,3,4,5,6,7
       referring to   E0,E1,M1,E2,M2,E3,M3,.. For example a M1+E2 transition would be written 304.
       A value of 0 means an unknown multipolarity.
    5)The multipolarity mixing ratio. O means that either the transition is a E1,M1,E2,M2 transition
        or the multipolarity mixing ratio is not given in ENSDF.
    6) Total internal conversion coefficient : alpha = Ic/Ig
     Note1: total transition is the sum of gamma de-excitation and internal
          conversion. Therefore total branching ratio is proportional to
          (1+alpha)*Ig
     Note2: total branching ratios from a given level do not always sum up to
          100%. They are re-normalized internally.
     Note3: relative probabilities for gamma de-excitation and internal conversion
          are 1/(1+alpha) and alpha/(1+alpha) respectively
    """
    l.alpha = float(words[5])
    return l


def add_ion_gamma_sources(sim, user_info, bins=200):
    """
    Consider an input 'fake' ion source with a given activity.
    Create a source of gamma for all decay daughters of this ion.

    The gamma spectrum is given according to the XXXX FIXME

    The activity intensity of all sources will be computed with Bateman
    equations during source initialisation, we only set the parameters here.

    """
    print("add all sources")

    # consider the user ion
    words = user_info.particle.split(" ")
    if not user_info.particle.startswith("ion") or len(words) != 3:
        gate.fatal(
            f"The 'ion' option of user_info must be 'ion Z A', while it is {user_info.ion}"
        )
    z = int(words[1])
    a = int(words[2])
    print("ion ", z, a)

    # get list of decay ions
    id = int(f"{z:3}{a:3}0000")
    print(id)
    first_nuclide = rd.Nuclide(id)
    print(first_nuclide)
    # print("half life", nuclide.half_life())
    daughters = get_all_nuclide_progeny(first_nuclide)
    daughters.append(first_nuclide.nuclide)
    print("all daughters (no order)", daughters)

    # loop to add all sources, we copy all options and update the info
    sources = []
    for daughter in daughters:
        s = sim.add_source(user_info.type_name, f"{user_info.name}_{daughter}")
        s.copy_from(user_info)
        # additional info, specific to ion gamma source
        nuclide = rd.Nuclide(daughter)
        s.particle = "gamma"
        # set gamma lines
        s.energy.type = "spectrum_lines"
        s.energy.ion_gamma_mother = Box({"z": z, "a": a})
        s.energy.ion_gamma_daughter = Box({"z": nuclide.Z, "a": nuclide.A})
        w, ene = gate.get_ion_gamma_channels(s.energy.ion_gamma_daughter)
        s.energy.spectrum_weight = w
        s.energy.spectrum_energy = ene
        # prepare times and activities that will be set during initialisation
        s.tac_from_decay_parameters = {
            "ion_name": first_nuclide,
            "daughter": daughter,
            "bins": bins,
        }
        sources.append(s)

    return sources


def get_tac_from_decay(
    ion_name, daugther_name, start_activity, start_time, end_time, bins
):
    """
    The following will be modified according to the TAC:
    ui.start_time, ui.end_time, ui.activity

    param is ui.tac_from_decay_parameters
    param is a dict with:
    - nuclide: a Nuclide object from radioactivedecay module, with the main ion
    - daughter: the daughter for which we compute the intensity in the time intervals
    - bins: number of bins for the discretised TAC

    - run_timing_intervals: is the list of time range from the Simulation
    """
    ion = rd.Inventory({ion_name: 1.0}, "Bq")
    sec = gate.g4_units("s")
    Bq = gate.g4_units("Bq")
    times = np.linspace(start_time, end_time, num=bins, endpoint=True)
    activities = []
    max_a = 0
    min_a = start_activity
    start_time = -1
    for t in times:
        x = ion.decay(t / sec, "s")
        intensity = x.activities()[daugther_name]
        a = intensity * start_activity
        activities.append(a)
        if start_time == -1 and a > 0:
            start_time = t
        if a > max_a:
            max_a = a
        if a < min_a:
            min_a = a
        # print(f"t {t/sec} {daugther_name} {intensity} {a/Bq}")
    print(
        f"{daugther_name} time range {start_time / sec}  {end_time / sec} "
        f": {start_time / sec} {min_a / Bq} {max_a / Bq}"
    )
    return times, activities
