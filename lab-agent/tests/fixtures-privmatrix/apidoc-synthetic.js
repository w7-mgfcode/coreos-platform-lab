// SYNTHETIC apidoc.js written for the unit tests of lab_agent.privmatrix.
// It follows the shape of the Proxmox API viewer file (an array assigned to apiSchema,
// followed by viewer code). It is not Proxmox data. The shape was compared with one real
// apidoc.js on 2026-11-16 (provenance of that file unverified).
const apiSchema = [
   {
      "children": [
         {
            "info": {
               "GET": {
                  "allowtoken": 1,
                  "permissions": {
                     "user": "all"
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/open",
            "text": "open"
         },
         {
            "info": {
               "GET": {
                  "allowtoken": 1,
                  "permissions": {
                     "user": "world"
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/world",
            "text": "world"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/vms/{vmid}",
                        [
                           "VM.PowerMgmt",
                           "VM.Config.Memory"
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/perm",
            "text": "perm"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/vms/{vmid}",
                        [
                           "VM.PowerMgmt",
                           "VM.Config.Memory"
                        ],
                        "any",
                        1
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/any",
            "text": "any"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "and",
                        [
                           "perm",
                           "/vms/{vmid}",
                           [
                              "VM.PowerMgmt"
                           ]
                        ],
                        [
                           "perm",
                           "/storage/{storage}",
                           [
                              "Datastore.Audit"
                           ]
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/and",
            "text": "and"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "or",
                        [
                           "perm",
                           "/vms/{vmid}",
                           [
                              "VM.Allocate"
                           ]
                        ],
                        [
                           "perm",
                           "/pool/{pool}",
                           [
                              "VM.Allocate"
                           ],
                           "require_param",
                           "pool"
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/or",
            "text": "or"
         },
         {
            "info": {
               "PUT": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm-modify",
                        "{path}"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/permmodify",
            "text": "permmodify"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "userid-param",
                        "self"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/useridself",
            "text": "useridself"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "userid-param",
                        "Realm.AllocateUser"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/useridpriv",
            "text": "useridpriv"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "userid-group",
                        [
                           "User.Modify"
                        ],
                        "groups_param",
                        "create"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/useridgroup",
            "text": "useridgroup"
         },
         {
            "info": {
               "GET": {
                  "allowtoken": 1
               }
            },
            "leaf": 1,
            "path": "/synthetic/nopermkey",
            "text": "nopermkey"
         },
         {
            "info": {
               "GET": {
                  "allowtoken": 1,
                  "permissions": {}
               }
            },
            "leaf": 1,
            "path": "/synthetic/emptyrule",
            "text": "emptyrule"
         },
         {
            "info": {
               "GET": {
                  "allowtoken": 1,
                  "permissions": {
                     "user": "somebody"
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/weirduser",
            "text": "weirduser"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "description": "You need 'VM.Backup' on /vms/{vmid}. The 'dumpdir' parameter is restricted to the root@pam user.",
                     "user": "all"
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/text",
            "text": "text"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/vms/{vmid}",
                        [
                           "VM.Clone"
                        ]
                     ],
                     "description": "You need 'VM.Clone' on /vms/{vmid}. You also need 'Datastore.AllocateSpace' on any used storage."
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/textextra",
            "text": "textextra"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/vms/{vmid}",
                        [
                           "VM.PowerMgmt"
                        ]
                     ],
                     "description": "Needs 'VM.PowerMgmt' on /vms/{vmid}."
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{vmid}/descsame",
            "text": "descsame"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm-future",
                        "/",
                        [
                           "Sys.Audit"
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/unknownform",
            "text": "unknownform"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/vms/{vmid}"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/badperm",
            "text": "badperm"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "and"
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/emptyand",
            "text": "emptyand"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/",
                        [
                           "Sys.Audit"
                        ],
                        "wat",
                        1
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/badoption",
            "text": "badoption"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 1,
                  "permissions": {
                     "user": "root@pam"
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/rootonly",
            "text": "rootonly"
         },
         {
            "info": {
               "POST": {
                  "allowtoken": 0,
                  "permissions": {
                     "check": [
                        "perm",
                        "/",
                        [
                           "Sys.Audit"
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/notoken",
            "text": "notoken"
         },
         {
            "info": {
               "GET": {
                  "allowtoken": 1,
                  "permissions": {
                     "check": [
                        "perm",
                        "/nodes/{mystery}",
                        [
                           "Sys.Audit"
                        ]
                     ]
                  }
               }
            },
            "leaf": 1,
            "path": "/synthetic/{mystery}/unbound",
            "text": "unbound"
         }
      ],
      "path": "/synthetic",
      "text": "synthetic"
   }
]
;

let method2cmd = {
    GET: 'get',
    POST: 'create',
};
throw new Error('this file must never be executed');
