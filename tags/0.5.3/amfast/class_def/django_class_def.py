from amfast import class_def

class DjangoDef(class_def.ClassDef):
    def getInstance(self):
        obj = super(self, class_def.ClassDef).getInstance()
        obj.__init__()
        return obj
