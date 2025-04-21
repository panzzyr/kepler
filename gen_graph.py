# функции для создания графового представления молекулы ПОМ
# в виде json'а на основе mol-файла
# TODO: сделать корректную обработку объединения двух
# металлов для диметаллических мостиков

import json
from pymol import cmd

# функция принимает идентификатор (id) атома в объекте
# ChemPy, возвращает идентификторы его соседей
# и их химические элементы
def sosedi(a_id):
    # просим PyMOL выдать незанятое имя для временного
    # выделения (selection)
    tempname = cmd.get_unused_name()
    # создаём временное выделение (всех соседей заданного атома)
    cmd.select(tempname, "neighbor "+"id "+str(a_id))
    s_ids = []
    s_elems = []
    # создаём списки идентификаторов и хим. элементов соседей
    for s in cmd.get_model(tempname).atom:
        s_ids.append(s.id)
        s_elems.append(s.symbol)
    # удаляем временное выделение, дабы не засорять
    # пространство имён
    cmd.delete(tempname)
    # сортируем списки (в лексикографическом порядке)
    s_ids.sort()
    s_elems.sort()
    # возвращаем в виде словаря
    return {"ids":s_ids, "elems":s_elems}


def atom2type(atom):
    return atom.symbol+str(len(sosedi(atom.id)["ids"]))


def atom2center(atom,centerNeighNum=7):
    return str(int(len(sosedi(atom.id)["ids"])==centerNeighNum))


def mol2graph(molName,outName,conCut=None):
    # переходные металлы:
    trMe = ["Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn","Y","Zr",
        "Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","Lu","Hf","Ta","W",
        "Re","Os","Ir","Pt","Au","Hg"]
    # болванка словаря для графа
    jGraph = {"graph":{"vertices":[],"edges":[]}}
    
    # имя объекта молекулы в PyMOL при загрузке файла molName
    molObjName = molName[:-4]
    # имя выделения только для связанных с чем-либо атомов
    bndName = "bonded_"+molObjName
    cmd.reinitialize()
    # ветка True требует тестирования:
    if conCut:
        cmd.set("connect_cutoff", conCut)
    cmd.load(molName)
    cmd.select(bndName, "bonded")
    # TODO: сделать проверку элементного состава выделенных атомов
    # TODO: бросать исключение, если что-то кроме металлов и кислорода
    # атомы металлов -- будущие центры вершин графа
    mtlAtoms = [s for s in cmd.get_model(bndName).atom if s.symbol 
    in trMe]
    for i in mtlAtoms:
        tp = atom2type(i)
        cntr = atom2center(i)
        ngh = []
        atIds = [i.id]
        atIds.extend([s for s in sosedi(i.id)["ids"]])
        #TODO: проверять все ли соседи кислороды, кидать исключение
        # если нет
        vert = {"type":tp, "is_center":cntr, 
        "neighs":ngh, "atom_ids":atIds}
        jGraph["graph"]["vertices"].append(vert)
    for i in range(len(jGraph["graph"]["vertices"])-1):
        for j in range(i+1, len(jGraph["graph"]["vertices"])):
            # TODO: вынести эту проверку соседства в отдельную функцию
            if len(set(jGraph["graph"]["vertices"][i]["atom_ids"]) &
            set(jGraph["graph"]["vertices"][j]["atom_ids"])):
                jGraph["graph"]["vertices"][i]["neighs"].append(j)
                jGraph["graph"]["vertices"][j]["neighs"].append(i)
                jGraph["graph"]["edges"].append([i,j])
    # типа debug:
    #print("len(jGraph[\"graph\"][\"vertices\"]", 
    #len(jGraph["graph"]["vertices"]))
    #cnt = 0
    #for v in jGraph["graph"]["vertices"]:        
    #    print(cnt, v, "\n")
    #    cnt += 1
    with open(outName, "w") as outjs:
        json.dump(jGraph, outjs)
        



